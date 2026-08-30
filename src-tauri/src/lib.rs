use serde::Serialize;
use std::{
    io::{Read, Write},
    net::{TcpListener, TcpStream},
    sync::{
        atomic::{AtomicBool, Ordering},
        Mutex,
    },
    thread,
    time::{Duration, Instant},
};
use tauri::{Manager, RunEvent};
use uuid::Uuid;
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

struct BackendRuntime {
    api_base: String,
    instance_id: String,
    shutdown_token: String,
    ready: AtomicBool,
    shutting_down: AtomicBool,
    last_error: Mutex<Option<String>>,
    child: Mutex<Option<CommandChild>>,
}

#[derive(Clone, Serialize)]
struct BackendRuntimeStatus {
    api_base: String,
    instance_id: String,
    ready: bool,
    last_error: Option<String>,
}

#[tauri::command]
fn backend_api_base(state: tauri::State<'_, BackendRuntime>) -> String {
    state.api_base.clone()
}

#[tauri::command]
fn backend_runtime_status(state: tauri::State<'_, BackendRuntime>) -> BackendRuntimeStatus {
    BackendRuntimeStatus {
        api_base: state.api_base.clone(),
        instance_id: state.instance_id.clone(),
        ready: state.ready.load(Ordering::SeqCst),
        last_error: state.last_error.lock().ok().and_then(|value| (*value).clone()),
    }
}

fn free_loopback_port() -> std::io::Result<u16> {
    let listener = TcpListener::bind(("127.0.0.1", 0))?;
    Ok(listener.local_addr()?.port())
}

fn nonce(label: &str) -> String {
    format!("{label}-{}", Uuid::new_v4())
}

fn http_exchange(port: u16, request: &str) -> std::io::Result<String> {
    let mut stream = TcpStream::connect(("127.0.0.1", port))?;
    stream.set_read_timeout(Some(Duration::from_millis(700)))?;
    stream.set_write_timeout(Some(Duration::from_millis(700)))?;
    stream.write_all(request.as_bytes())?;
    stream.flush()?;
    let mut response = String::new();
    stream.read_to_string(&mut response)?;
    Ok(response)
}

fn health_matches(port: u16, instance_id: &str) -> bool {
    let request = format!(
        "GET /api/v1/health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n"
    );
    http_exchange(port, &request)
        .map(|response| {
            response.starts_with("HTTP/1.1 200")
                && response.contains("\"status\":\"ok\"")
                && response.contains(instance_id)
        })
        .unwrap_or(false)
}

fn wait_for_health(port: u16, instance_id: &str, timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if health_matches(port, instance_id) {
            return true;
        }
        thread::sleep(Duration::from_millis(100));
    }
    false
}

fn request_graceful_shutdown(port: u16, token: &str) -> bool {
    let request = format!(
        concat!(
            "POST /api/v1/runtime/shutdown HTTP/1.1\r\n",
            "Host: 127.0.0.1:{port}\r\n",
            "X-Economy-Lab-Shutdown-Token: {token}\r\n",
            "Content-Length: 0\r\n",
            "Connection: close\r\n\r\n"
        )
    );
    http_exchange(port, &request)
        .map(|response| response.starts_with("HTTP/1.1 200"))
        .unwrap_or(false)
}

fn wait_until_stopped(port: u16, timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if TcpStream::connect(("127.0.0.1", port)).is_err() {
            return true;
        }
        thread::sleep(Duration::from_millis(80));
    }
    false
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            backend_api_base,
            backend_runtime_status
        ])
        .setup(|app| {
            let port = free_loopback_port()?;
            let api_base = format!("http://127.0.0.1:{port}");
            let data_dir = app.path().app_data_dir()?;
            std::fs::create_dir_all(&data_dir)?;
            let instance_id = nonce("economy-lab");
            let shutdown_token = nonce("shutdown");

            let sidecar_args = vec![
                "--host".to_string(),
                "127.0.0.1".to_string(),
                "--port".to_string(),
                port.to_string(),
                "--log-level".to_string(),
                "warning".to_string(),
            ];
            let spawn_result = app
                .shell()
                .sidecar("economy-lab-backend")
                .and_then(|command| {
                    command
                        .args(sidecar_args)
                        .env("ECONOMY_LAB_RUNTIME_MODE", "desktop-sidecar")
                        .env("ECONOMY_LAB_RUNTIME_INSTANCE", &instance_id)
                        .env("ECONOMY_LAB_SHUTDOWN_TOKEN", &shutdown_token)
                        .env("ECONOMY_LAB_DATA_DIR", data_dir.to_string_lossy().to_string())
                        .spawn()
                });

            let (receiver, child, spawn_error) = match spawn_result {
                Ok((receiver, child)) => (Some(receiver), Some(child), None),
                Err(error) => (None, None, Some(error.to_string())),
            };

            app.manage(BackendRuntime {
                api_base: api_base.clone(),
                instance_id: instance_id.clone(),
                shutdown_token,
                ready: AtomicBool::new(false),
                shutting_down: AtomicBool::new(false),
                last_error: Mutex::new(spawn_error.clone()),
                child: Mutex::new(child),
            });

            if let Some(mut receiver) = receiver {
                let handle = app.handle().clone();
                tauri::async_runtime::spawn(async move {
                    while let Some(event) = receiver.recv().await {
                        match event {
                            CommandEvent::Stderr(bytes) => {
                                eprintln!(
                                    "Economy Lab backend: {}",
                                    String::from_utf8_lossy(&bytes)
                                );
                            }
                            CommandEvent::Error(error) => {
                                let state = handle.state::<BackendRuntime>();
                                state.ready.store(false, Ordering::SeqCst);
                                if let Ok(mut slot) = state.last_error.lock() {
                                    *slot = Some(error);
                                }
                            }
                            CommandEvent::Terminated(payload) => {
                                let state = handle.state::<BackendRuntime>();
                                state.ready.store(false, Ordering::SeqCst);
                                if !state.shutting_down.load(Ordering::SeqCst) {
                                    if let Ok(mut slot) = state.last_error.lock() {
                                        *slot = Some(format!(
                                            "Backend encerrado inesperadamente (code={:?}, signal={:?})",
                                            payload.code, payload.signal
                                        ));
                                    }
                                }
                            }
                            _ => {}
                        }
                    }
                });
            }

            if spawn_error.is_none() && wait_for_health(port, &instance_id, Duration::from_secs(30)) {
                app.state::<BackendRuntime>()
                    .ready
                    .store(true, Ordering::SeqCst);
            } else if spawn_error.is_none() {
                if let Ok(mut slot) = app.state::<BackendRuntime>().last_error.lock() {
                    *slot = Some("Backend não respondeu ao health check em 30 segundos".into());
                }
            }

            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Economy Lab");

    app.run(|handle, event| {
        if let RunEvent::ExitRequested { api, code, .. } = event {
            let state = handle.state::<BackendRuntime>();
            if !state.shutting_down.swap(true, Ordering::SeqCst) {
                api.prevent_exit();
                let port = state
                    .api_base
                    .rsplit(':')
                    .next()
                    .and_then(|value| value.parse::<u16>().ok())
                    .unwrap_or(0);
                let token = state.shutdown_token.clone();
                let handle = handle.clone();
                let exit_code = code.unwrap_or(0);

                thread::spawn(move || {
                    if port != 0 {
                        let _ = request_graceful_shutdown(port, &token);
                        let _ = wait_until_stopped(port, Duration::from_secs(3));
                    }

                    // Fallback for a hung backend. A graceful API shutdown is preferred
                    // because one-file Python packagers can create helper processes.
                    let state = handle.state::<BackendRuntime>();
                    if let Ok(mut child) = state.child.lock() {
                        if let Some(process) = child.take() {
                            let _ = process.kill();
                        }
                    }
                    handle.exit(exit_code);
                });
            }
        }
    });
}
