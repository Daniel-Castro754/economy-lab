from economy_lab.abm.economy_zero import EconomyZeroConfig, EconomyZeroModel
from economy_lab.core.coupling import HybridMacroCoupler
from economy_lab.core.execution import SimulationExecutionControl
from economy_lab.core.authority import (
    AuthoritySession,
    runtime_source_from_activation_name,
    runtime_source_from_household_name,
)
from economy_lab.core.shocks import EconomicShock
from economy_lab.core.state import EconomyState
from economy_lab.core.macro_cycle import (
    derive_dynare_reference_settings,
    extract_quarterly_macro_state,
)
from economy_lab.core.schemas import (
    AccountingReport,
    AuthorityReport,
    BankStatusView,
    BankingReport,
    CouplingPoint,
    CouplingReport,
    EngineTrace,
    FinancialControlView,
    FinancialEngineReport,
    HouseholdEngineReport,
    HouseholdIncomeGroupView,
    LaborMarketReport,
    MatrixRowView,
    MacroIRFPoint,
    MacroReport,
    MacroRecalibrationPoint,
    MacroRecalibrationReport,
    MacroStateSnapshot,
    ScenarioSpec,
    ShockReport,
    ShockScheduleView,
    SectorBalanceSheetView,
    SimulationResult,
    SimulationSummary,
    TimePoint,
)
from economy_lab.engines.dynare_adapter import run_reference_nk_model
from economy_lab.finance import (
    FinancialGuidance,
    aggregate_capital_ratio,
    bank_financials,
    flow_matrix,
    sector_balance_sheets,
    stock_matrix,
)


def run_demo_simulation(
    spec: ScenarioSpec,
    execution_control: SimulationExecutionControl | None = None,
) -> SimulationResult:
    """Legacy architecture demo kept for comparison and API compatibility."""

    gdp = spec.initial_gdp
    inflation = spec.initial_inflation
    unemployment = spec.initial_unemployment
    neutral_rate = 8.0
    neutral_tax = 20.0
    points: list[TimePoint] = []

    if execution_control is not None:
        execution_control.checkpoint("preparing", progress=2.0)

    for month in range(1, spec.months + 1):
        if execution_control is not None:
            execution_control.checkpoint(
                "simulating",
                completed_steps=month - 1,
                total_steps=spec.months,
                progress=5.0 + 85.0 * (month - 1) / spec.months,
            )
        monetary_gap = spec.policy_rate - neutral_rate
        tax_gap = spec.income_tax - neutral_tax
        fiscal_impulse = spec.public_spending_change
        monthly_growth_pct = 0.15 - 0.025 * monetary_gap - 0.008 * tax_gap + 0.018 * fiscal_impulse
        gdp *= 1 + monthly_growth_pct / 100
        demand_pressure = (gdp / spec.initial_gdp - 1) * 10
        inflation += -0.012 * monetary_gap + 0.004 * fiscal_impulse + 0.005 * demand_pressure
        inflation = max(-20.0, min(100.0, inflation))
        unemployment += -0.035 * monthly_growth_pct
        unemployment = max(0.0, min(100.0, unemployment))
        points.append(
            TimePoint(
                month=month,
                gdp_index=round(gdp, 3),
                inflation=round(inflation, 3),
                unemployment=round(unemployment, 3),
                policy_rate=spec.policy_rate,
            )
        )

        if execution_control is not None:
            execution_control.checkpoint(
                "simulating",
                completed_steps=month,
                total_steps=spec.months,
                progress=5.0 + 85.0 * month / spec.months,
            )

    final = points[-1]
    shock_report = ShockReport(
        schedules=[
            ShockScheduleView(
                kind=shock.kind,
                start_month=shock.start_month,
                duration_months=shock.duration_months,
                magnitude_pct=shock.magnitude_pct,
                label=shock.label,
            )
            for shock in spec.shocks
        ],
        warning=(
            "Choques v1.0 são impulsos exógenos auditáveis e limitados. Eles alteram comportamento/fluxos "
            "por regras explícitas, não representam elasticidades estimadas em dados reais."
        ),
    ) if spec.shocks else None

    result = SimulationResult(
        scenario=spec.name,
        model="architecture-demo-v0",
        warning="Modelo demonstrativo não calibrado; não interpretar os números economicamente.",
        series=points,
        engines=EngineTrace(
            activation="demo-loop",
            household_decision="demo-rule",
        ),
        summary=SimulationSummary(
            final_gdp_index=final.gdp_index,
            final_inflation=final.inflation,
            final_unemployment=final.unemployment,
        ),
    )
    if execution_control is not None:
        execution_control.checkpoint(
            "finalized", completed_steps=spec.months, total_steps=spec.months, progress=98.0
        )
    return result


def run_economy_zero(
    spec: ScenarioSpec,
    execution_control: SimulationExecutionControl | None = None,
) -> SimulationResult:
    if execution_control is not None:
        execution_control.checkpoint("preparing", progress=1.0)
    config = EconomyZeroConfig(
        households=spec.households,
        firms=spec.firms,
        banks=spec.banks,
        seed=spec.seed,
        initial_employment_rate=max(0.05, min(1.0, 1.0 - spec.initial_unemployment / 100.0)),
        income_tax_rate=spec.income_tax / 100.0,
        public_spending_change=spec.public_spending_change / 100.0,
        policy_rate=spec.policy_rate / 100.0,
        activation_engine=spec.activation_engine,
        mesa_activation_pattern=spec.mesa_activation_pattern,
        household_shopping_sample_size=spec.household_shopping_sample_size,
        household_cheapest_choice_probability=spec.household_cheapest_choice_probability,
        firm_price_adjustment_strength=spec.firm_price_adjustment_strength,
        firm_hiring_strength=spec.firm_hiring_strength,
        firm_layoff_strength=spec.firm_layoff_strength,
        labor_matching_efficiency=spec.labor_matching_efficiency,
        initial_capital_per_worker=spec.initial_capital_per_worker,
        capital_unit_cost=spec.capital_unit_cost,
        annual_capital_depreciation_rate=spec.annual_capital_depreciation_rate / 100.0,
        firm_investment_propensity=spec.firm_investment_propensity / 100.0,
        capital_output_elasticity=spec.capital_output_elasticity,
        household_behavior=spec.household_behavior,
        hark_crra=spec.hark_crra,
        hark_annual_discount_factor=spec.hark_annual_discount_factor,
        hark_state_mode=spec.hark_state_mode,
        hark_unemployment_probability=spec.hark_unemployment_probability,
        hark_unemployment_replacement_rate=spec.hark_unemployment_replacement_rate,
        hark_permanent_shock_std=spec.hark_permanent_shock_std,
        hark_transitory_shock_std=spec.hark_transitory_shock_std,
        hark_permanent_income_memory=spec.hark_permanent_income_memory,
        hark_income_groups=spec.hark_income_groups,
        hark_income_risk_dispersion=spec.hark_income_risk_dispersion,
        unemployment_benefits_enabled=spec.unemployment_benefits_enabled,
        unemployment_benefit_replacement_rate=spec.unemployment_benefit_replacement_rate / 100.0,
        unemployment_benefit_waiting_months=spec.unemployment_benefit_waiting_months,
        unemployment_benefit_max_months=spec.unemployment_benefit_max_months,
        unemployment_benefit_cap=spec.unemployment_benefit_cap,
        labor_supply_mode=spec.labor_supply_mode,
        labor_search_intensity=spec.labor_search_intensity,
        reservation_wage_ratio=spec.reservation_wage_ratio,
        benefit_search_disincentive=spec.benefit_search_disincentive,
        wealth_search_disincentive=spec.wealth_search_disincentive,
        job_separation_risk_memory=spec.job_separation_risk_memory,
        minimum_bank_capital_ratio=spec.minimum_bank_capital_ratio / 100.0,
        target_reserve_ratio=spec.target_reserve_ratio / 100.0,
        credit_supply_factor=spec.bank_credit_supply_factor,
        default_writeoff_ratio=spec.default_writeoff_ratio / 100.0,
        interbank_spread=spec.interbank_spread / 100.0,
        central_bank_penalty_spread=spec.central_bank_penalty_spread / 100.0,
        household_credit_enabled=spec.household_credit_enabled,
        household_credit_income_multiple=spec.household_credit_income_multiple,
        household_credit_liquidity_target_months=spec.household_credit_liquidity_target_months,
        household_credit_spread=spec.household_credit_spread / 100.0,
        household_principal_repayment_rate=spec.household_principal_repayment_rate / 100.0,
        household_default_writeoff_ratio=spec.household_default_writeoff_ratio / 100.0,
        bank_resolution_mode=spec.bank_resolution_mode,
        bank_resolution_trigger_ratio=spec.bank_resolution_trigger_ratio / 100.0,
        bank_resolution_target_ratio=spec.bank_resolution_target_ratio / 100.0,
        bail_in_household_protection=spec.bail_in_household_protection,
        bail_in_firm_protection=spec.bail_in_firm_protection,
        financial_guidance=tuple(
            FinancialGuidance(
                month=item.month,
                minimum_capital_ratio=item.minimum_bank_capital_ratio / 100.0,
                target_reserve_ratio=item.target_reserve_ratio / 100.0,
                credit_supply_factor=item.credit_supply_factor,
                default_writeoff_ratio=item.default_writeoff_ratio / 100.0,
                interbank_spread=item.interbank_spread / 100.0,
                central_bank_penalty_spread=item.central_bank_penalty_spread / 100.0,
            )
            for item in spec.financial_guidance
        ),
        shocks=tuple(
            EconomicShock(
                kind=shock.kind,
                start_month=shock.start_month,
                duration_months=shock.duration_months,
                magnitude_pct=shock.magnitude_pct,
                label=shock.label,
            )
            for shock in spec.shocks
        ),
    )
    model = EconomyZeroModel(config)
    if execution_control is not None:
        execution_control.checkpoint("preparing", progress=4.0)
    authority_session = AuthoritySession(spec, strict=True)

    macro_run = None
    coupler = None
    recalibration_events: list[tuple[object, object]] = []
    if spec.macro_engine == "dynare":
        macro_run = run_reference_nk_model(
            irf_periods=spec.dynare_irf_periods,
            monetary_shock_pp=spec.dynare_monetary_shock_bp / 100.0,
            neutral_nominal_rate=spec.dynare_neutral_nominal_rate,
            beta=spec.dynare_beta,
            sigma=spec.dynare_sigma,
            kappa=spec.dynare_kappa,
            rho_i=spec.dynare_rho_i,
            phi_pi=spec.dynare_phi_pi,
            phi_x=spec.dynare_phi_x,
            timeout_seconds=(
                execution_control.remaining_seconds(120.0)
                if execution_control is not None
                else 120
            ),
        )
        if spec.macro_coupling == "hybrid":
            coupler = HybridMacroCoupler(
                points=macro_run.points,
                base_policy_rate_pct=spec.policy_rate,
                inflation_anchor_pct=spec.initial_inflation,
                coupling_strength=spec.macro_coupling_strength,
                feedback_strength=spec.macro_feedback_strength,
                bank_count=spec.banks,
            )

    activation_authority = runtime_source_from_activation_name(model.activation_runtime.name)
    household_authority = runtime_source_from_household_name(model.consumption_policy.name)
    financial_authority = (
        "minsky_profile" if spec.financial_engine == "minsky_profile" else "native_finance"
    )
    authority_session.claim_run_bindings(
        activation_source=activation_authority,
        household_source=household_authority,
        financial_source=financial_authority,
        dynare_active=spec.macro_engine == "dynare",
    )

    if coupler is None:
        metrics = []
        for month in range(1, spec.months + 1):
            if execution_control is not None:
                execution_control.checkpoint(
                    "simulating",
                    completed_steps=month - 1,
                    total_steps=spec.months,
                    progress=5.0 + 85.0 * (month - 1) / spec.months,
                )
            item = model.step()
            metrics.append(item)
            canonical_state = EconomyState.from_runtime_metrics(
                item,
                activation_source=activation_authority,
                household_policy_source=household_authority,
                financial_control_source=financial_authority,
                macro_policy_source="scenario_central_bank",
            )
            authority_session.claim_tick(state=canonical_state)
            if execution_control is not None:
                execution_control.checkpoint(
                    "simulating",
                    completed_steps=month,
                    total_steps=spec.months,
                    progress=5.0 + 85.0 * month / spec.months,
                )
    else:
        metrics = []
        for month in range(1, spec.months + 1):
            if execution_control is not None:
                execution_control.checkpoint(
                    "simulating",
                    completed_steps=month - 1,
                    total_steps=spec.months,
                    progress=5.0 + 85.0 * (month - 1) / spec.months,
                )
            signal = coupler.signal_for_month(month)
            model.apply_macro_guidance(
                policy_rate_pct=signal.applied_policy_rate_pct,
                demand_signal_pp=signal.demand_signal_pp,
                inflation_signal_pp=signal.price_signal_pp,
            )
            month_metrics = model.step()
            coupler.observe(signal=signal, metrics=month_metrics)
            metrics.append(month_metrics)
            canonical_state = EconomyState.from_runtime_metrics(
                month_metrics,
                activation_source=activation_authority,
                household_policy_source=household_authority,
                financial_control_source=financial_authority,
                macro_policy_source="hybrid_coupler",
            )
            authority_session.claim_tick(state=canonical_state)

            should_recalibrate = (
                spec.macro_recalibration == "quarterly"
                and month % 3 == 0
                and month < spec.months
                and len(recalibration_events) < spec.macro_max_recalibrations
            )
            if should_recalibrate:
                quarter = month // 3
                quarter_metrics = metrics[max(0, month - 3):month]
                previous_endpoint = metrics[month - 4] if month > 3 else None
                state = extract_quarterly_macro_state(
                    quarter_metrics,
                    quarter=quarter,
                    bank_count=spec.banks,
                    previous_endpoint=previous_endpoint,
                )
                settings = derive_dynare_reference_settings(
                    state,
                    initial_monetary_shock_pp=spec.dynare_monetary_shock_bp / 100.0,
                    inflation_anchor_pct=spec.initial_inflation,
                    unemployment_anchor_pct=spec.initial_unemployment,
                    adaptation_strength=spec.macro_recalibration_strength,
                    base_beta=spec.dynare_beta,
                    base_sigma=spec.dynare_sigma,
                    base_kappa=spec.dynare_kappa,
                    base_rho_i=spec.dynare_rho_i,
                    base_phi_pi=spec.dynare_phi_pi,
                    base_phi_x=spec.dynare_phi_x,
                )
                macro_run = run_reference_nk_model(
                    irf_periods=spec.dynare_irf_periods,
                    monetary_shock_pp=settings.monetary_shock_pp,
                    neutral_nominal_rate=settings.base_policy_rate_pct,
                    beta=settings.beta,
                    sigma=settings.sigma,
                    kappa=settings.kappa,
                    rho_i=settings.rho_i,
                    phi_pi=settings.phi_pi,
                    phi_x=settings.phi_x,
                    timeout_seconds=(
                        execution_control.remaining_seconds(120.0)
                        if execution_control is not None
                        else 120
                    ),
                )
                coupler.replace_guidance(
                    points=macro_run.points,
                    start_month=month + 1,
                    base_policy_rate_pct=settings.base_policy_rate_pct,
                )
                recalibration_events.append((state, settings))

            if execution_control is not None:
                execution_control.checkpoint(
                    "simulating",
                    completed_steps=month,
                    total_steps=spec.months,
                    progress=5.0 + 85.0 * month / spec.months,
                )

    if execution_control is not None:
        execution_control.checkpoint(
            "finalizing", completed_steps=spec.months, total_steps=spec.months, progress=92.0
        )
    authority_session.assert_complete(len(metrics))
    authority_report = AuthorityReport(**authority_session.audit(ticks=len(metrics)).to_dict())

    points = [
        TimePoint(
            month=item.month,
            gdp_index=round(item.gdp_index, 3),
            inflation=round(item.inflation, 3),
            unemployment=round(item.unemployment, 3),
            policy_rate=round(item.policy_rate, 3),
            price_index=round(item.price_index, 4),
            household_consumption=round(item.household_consumption, 2),
            government_spending=round(item.government_spending, 2),
            corporate_debt=round(item.corporate_debt, 2),
            bank_credit=round(item.bank_credit, 2),
            bank_deposits=round(item.bank_deposits, 2),
            gini_wealth=round(item.gini_wealth, 4),
            firm_defaults=item.firm_defaults,
            bank_reserves=round(item.bank_reserves, 2),
            central_bank_advances=round(item.central_bank_advances, 2),
            government_debt=round(item.government_debt, 2),
            private_net_financial_wealth=round(item.private_net_financial_wealth, 2),
            bank_capital=round(item.bank_capital, 2),
            bank_capital_ratio=round(100.0 * item.bank_capital_ratio, 3),
            undercapitalized_banks=item.undercapitalized_banks,
            interbank_credit=round(item.interbank_credit, 2),
            bank_profit_loss=round(item.bank_profit_loss, 2),
            credit_rationed=round(item.credit_rationed, 2),
            default_losses=round(item.default_losses, 2),
            exports=round(item.exports, 2),
            imports=round(item.imports, 2),
            net_exports=round(item.net_exports, 2),
            business_investment=round(item.business_investment, 2),
            productive_capital=round(item.productive_capital, 2),
            household_debt=round(item.household_debt, 2),
            household_credit=round(item.household_credit, 2),
            household_defaults=item.household_defaults,
            bank_resolutions=item.bank_resolutions,
            public_recapitalization=round(item.public_recapitalization, 2),
            bail_in_losses=round(item.bail_in_losses, 2),
            unemployment_benefits=round(item.unemployment_benefits, 2),
            labor_force_participation=round(item.labor_force_participation, 3),
            job_separation_rate=round(item.job_separation_rate, 4),
            job_finding_rate=round(item.job_finding_rate, 4),
            active_shocks={key: round(value, 6) for key, value in item.active_shocks.items()},
        )
        for item in metrics
    ]
    final = points[-1]
    model.ledger.assert_balanced()
    sheets = sector_balance_sheets(model.ledger)
    stocks = stock_matrix(model.ledger, tick=model.tick)
    flows = flow_matrix(model.ledger, tick=model.tick)
    accounting = AccountingReport(
        tick=model.tick,
        sector_balance_sheets=[
            SectorBalanceSheetView(
                sector=item.sector,
                assets=round(item.assets, 6),
                liabilities=round(item.liabilities, 6),
                net_financial_worth=round(item.net_financial_worth, 6),
                positions={key: round(value, 6) for key, value in item.positions.items()},
            )
            for item in sheets
        ],
        stock_rows=[
            MatrixRowView(
                instrument=row.instrument,
                sectors={key: round(value, 6) for key, value in row.sectors.items()},
                total=round(row.total, 9),
            )
            for row in stocks.rows
        ],
        flow_rows=[
            MatrixRowView(
                instrument=row.instrument,
                sectors={key: round(value, 6) for key, value in row.sectors.items()},
                total=round(row.total, 9),
            )
            for row in flows.rows
        ],
        stocks_balanced=stocks.balanced,
        flows_balanced=flows.balanced,
    )
    bank_reports = [bank_financials(model.ledger, bank.id) for bank in model.banks]
    banking = BankingReport(
        aggregate_capital=round(sum(item.regulatory_capital for item in bank_reports), 6),
        aggregate_capital_ratio=round(100.0 * aggregate_capital_ratio(bank_reports), 6),
        undercapitalized_banks=sum(
            not item.compliant(config.minimum_bank_capital_ratio) for item in bank_reports
        ),
        aggregate_household_loans=round(sum(item.household_loans for item in bank_reports), 6),
        total_resolutions=sum(bank.resolutions for bank in model.banks),
        banks=[
            BankStatusView(
                bank_id=item.bank_id,
                reserves=round(item.reserves, 6),
                deposits=round(item.deposits, 6),
                corporate_loans=round(item.corporate_loans, 6),
                household_loans=round(item.household_loans, 6),
                interbank_assets=round(item.interbank_assets, 6),
                interbank_borrowing=round(item.interbank_borrowing, 6),
                central_bank_borrowing=round(item.central_bank_borrowing, 6),
                paid_in_equity=round(item.paid_in_equity, 6),
                retained_earnings=round(item.retained_earnings, 6),
                regulatory_capital=round(item.regulatory_capital, 6),
                risk_weighted_assets=round(item.risk_weighted_assets, 6),
                capital_ratio=round(100.0 * item.capital_ratio, 6),
                minimum_capital_ratio=round(100.0 * model.financial_controls.minimum_capital_ratio, 6),
                compliant=item.compliant(model.financial_controls.minimum_capital_ratio),
                resolutions=model.banks[item.bank_id].resolutions,
                last_resolution_mode=model.banks[item.bank_id].last_resolution_mode,
            )
            for item in bank_reports
        ],
    )

    financial_report = FinancialEngineReport(
        engine=("minsky-profile-controller-v1.0" if spec.financial_engine == "minsky_profile" else "economy-lab-native-finance-v1.0"),
        mode=("active-profile-path" if spec.financial_engine == "minsky_profile" and spec.financial_guidance else "active-profile-static" if spec.financial_engine == "minsky_profile" else "native"),
        profile_id=spec.applied_profiles.get("financial"),
        current=FinancialControlView(
            minimum_bank_capital_ratio=round(100.0 * model.financial_controls.minimum_capital_ratio, 6),
            target_reserve_ratio=round(100.0 * model.financial_controls.target_reserve_ratio, 6),
            credit_supply_factor=round(model.financial_controls.credit_supply_factor, 6),
            default_writeoff_ratio=round(100.0 * model.financial_controls.default_writeoff_ratio, 6),
            interbank_spread=round(100.0 * model.financial_controls.interbank_spread, 6),
            central_bank_penalty_spread=round(100.0 * model.financial_controls.central_bank_penalty_spread, 6),
        ),
        guidance_points=list(spec.financial_guidance),
        warning=(
            "O Minsky Profile fornece uma trajetória determinística e validada de controles bancários; "
            "o Economy Lab continua sendo a fonte da verdade contábil e nunca aceita saldos externos diretamente."
            if spec.financial_engine == "minsky_profile"
            else "Controles financeiros nativos do Economy Lab."
        ),
    )

    macro_report = None
    if macro_run is not None:
        macro_report = MacroReport(
            engine="dynare-octave",
            model_name=macro_run.model_name,
            model_kind=macro_run.model_kind,
            period_unit=macro_run.period_unit,
            shock_name=macro_run.shock_name,
            shock_size_pp=macro_run.shock_size_pp,
            neutral_nominal_rate=macro_run.neutral_nominal_rate,
            parameters={
                "beta": macro_run.beta,
                "sigma": macro_run.sigma,
                "kappa": macro_run.kappa,
                "rho_i": macro_run.rho_i,
                "phi_pi": macro_run.phi_pi,
                "phi_x": macro_run.phi_x,
            },
            irf=[
                MacroIRFPoint(
                    period=point.period,
                    output_gap=round(point.output_gap, 8),
                    inflation_gap=round(point.inflation_gap, 8),
                    policy_rate_gap=round(point.policy_rate_gap, 8),
                )
                for point in macro_run.points
            ],
            coupling_mode=(
                "hybrid-quarterly-resolve"
                if spec.macro_coupling == "hybrid" and spec.macro_recalibration == "quarterly"
                else "hybrid-feedback"
                if spec.macro_coupling == "hybrid"
                else "advisory-only"
            ),
            warning=(
                "Dynare fornece uma resposta estrutural marginal. PIB, inflação, emprego e balanços "
                "realizados continuam sob autoridade do ABM/SFC. No modo quarterly da v1.0 o modelo "
                "de referência é reexecutado após cada trimestre com ajustes pequenos, limitados e "
                "rastreáveis; isso é condicionamento experimental, não estimação DSGE online."
            ),
        )

    coupling_report = None
    if coupler is not None:
        coupling_report = CouplingReport(
            mode=("hybrid-quarterly-resolve-v1.0" if spec.macro_recalibration == "quarterly" else "hybrid-feedback-v1.0"),
            authority={
                "realized_gdp_inflation_unemployment": "economy-zero-abm",
                "credit_and_balance_sheets": "economy-lab-sfc-ledger",
                "structural_irf": "dynare-reference-nk",
                "translation_and_feedback": "economy-lab-hybrid-coupler-v1.0",
            },
            parameters={
                "coupling_strength": spec.macro_coupling_strength,
                "feedback_strength": spec.macro_feedback_strength,
                "recalibration_strength": spec.macro_recalibration_strength if spec.macro_recalibration == "quarterly" else 0.0,
            },
            points=[
                CouplingPoint(
                    month=item.month,
                    output_gap_guidance_pp=round(item.output_gap_guidance_pp, 8),
                    inflation_guidance_pp=round(item.inflation_guidance_pp, 8),
                    dynare_policy_gap_pp=round(item.dynare_policy_gap_pp, 8),
                    feedback_policy_gap_pp=round(item.feedback_policy_gap_pp, 8),
                    applied_policy_rate_pct=round(item.applied_policy_rate_pct, 8),
                    demand_signal_pp=round(item.demand_signal_pp, 8),
                    price_signal_pp=round(item.price_signal_pp, 8),
                    realized_gdp_index=round(item.realized_gdp_index, 8),
                    realized_output_gap_proxy_pp=round(item.realized_output_gap_proxy_pp, 8),
                    realized_inflation_pct=round(item.realized_inflation_pct, 8),
                    realized_unemployment_pct=round(item.realized_unemployment_pct, 8),
                    financial_stress=round(item.financial_stress, 8),
                    output_residual_pp=round(item.output_residual_pp, 8),
                    inflation_residual_pp=round(item.inflation_residual_pp, 8),
                )
                for item in coupler.observations
            ],
            warning=(
                "O output gap realizado é um proxy cíclico baseado em tendência EWMA, não uma "
                "estimativa de produto potencial. Os pesos de acoplamento são experimentais e "
                "precisam de calibração antes de qualquer interpretação empírica."
            ),
        )

    recalibration_report = None
    if spec.macro_recalibration == "quarterly" and coupler is not None:
        recalibration_report = MacroRecalibrationReport(
            mode="quarterly-state-conditioned-v1.0",
            frequency_months=3,
            adaptation_strength=spec.macro_recalibration_strength,
            completed_recalibrations=len(recalibration_events),
            runs=[
                MacroRecalibrationPoint(
                    quarter=state.quarter,
                    trigger_month=state.end_month,
                    next_start_month=settings.start_month,
                    effective_monetary_shock_pp=round(settings.monetary_shock_pp, 8),
                    base_policy_rate_pct=round(settings.base_policy_rate_pct, 8),
                    parameters={
                        "beta": settings.beta,
                        "sigma": round(settings.sigma, 8),
                        "kappa": round(settings.kappa, 8),
                        "rho_i": round(settings.rho_i, 8),
                        "phi_pi": round(settings.phi_pi, 8),
                        "phi_x": round(settings.phi_x, 8),
                    },
                    state=MacroStateSnapshot(
                        quarter=state.quarter,
                        end_month=state.end_month,
                        gdp_index=round(state.gdp_index, 8),
                        quarterly_gdp_growth_pct=round(state.quarterly_gdp_growth_pct, 8),
                        inflation_pct=round(state.inflation_pct, 8),
                        unemployment_pct=round(state.unemployment_pct, 8),
                        policy_rate_pct=round(state.policy_rate_pct, 8),
                        bank_credit=round(state.bank_credit, 8),
                        quarterly_credit_growth_pct=round(state.quarterly_credit_growth_pct, 8),
                        bank_capital_ratio_pct=round(state.bank_capital_ratio_pct, 8),
                        financial_stress=round(state.financial_stress, 8),
                    ),
                )
                for state, settings in recalibration_events
            ],
            warning=(
                "Os coeficientes são condicionados por uma regra bounded e transparente apenas para "
                "provar a orquestração trimestral. Eles não foram estimados em dados e não devem ser "
                "interpretados como parâmetros estruturais variantes no tempo."
            ),
        )

    shock_report = ShockReport(
        schedules=[
            ShockScheduleView(
                kind=shock.kind,
                start_month=shock.start_month,
                duration_months=shock.duration_months,
                magnitude_pct=shock.magnitude_pct,
                label=shock.label,
            )
            for shock in spec.shocks
        ],
        warning=(
            "Choques v1.0 são impulsos exógenos auditáveis e limitados. Eles alteram comportamento/fluxos "
            "por regras explícitas, não representam elasticidades estimadas em dados reais."
        ),
    ) if spec.shocks else None

    household_engine_report = None
    if spec.household_behavior == "hark":
        group_views: list[HouseholdIncomeGroupView] = []
        for group in range(spec.hark_income_groups):
            members = [household for household in model.households if household.income_group == group]
            if not members:
                continue
            group_views.append(
                HouseholdIncomeGroupView(
                    group=group + 1,
                    households=len(members),
                    employment_rate=round(100.0 * sum(item.employed_by is not None for item in members) / len(members), 4),
                    average_wage=round(sum(item.wage for item in members) / len(members), 4),
                    average_permanent_income=round(sum(item.permanent_income_estimate for item in members) / len(members), 4),
                    average_transitory_income_ratio=round(sum(item.transitory_income_ratio for item in members) / len(members), 6),
                    average_unemployment_probability=round(100.0 * sum(item.unemployment_probability for item in members) / len(members), 4),
                    average_consumption=round(sum(item.last_consumption for item in members) / len(members), 4),
                    average_deposit=round(sum(max(0.0, model.ledger.balance(item.deposit_account)) for item in members) / len(members), 4),
                    average_unemployment_benefit=round(sum(item.last_unemployment_benefit for item in members) / len(members), 4),
                    labor_force_participation=round(100.0 * sum(item.employed_by is not None or item.labor_force_participating for item in members) / len(members), 4),
                    average_reservation_wage=round(sum(item.reservation_wage for item in members) / len(members), 4),
                    average_search_intensity=round(sum(item.search_intensity for item in members) / len(members), 6),
                )
            )
        all_households = model.households
        household_engine_report = HouseholdEngineReport(
            engine=model.consumption_policy.name,
            state_mode=spec.hark_state_mode,
            income_groups=spec.hark_income_groups,
            employment_rate=round(100.0 * sum(item.employed_by is not None for item in all_households) / max(1, len(all_households)), 4),
            average_permanent_income=round(sum(item.permanent_income_estimate for item in all_households) / max(1, len(all_households)), 4),
            average_transitory_income_ratio=round(sum(item.transitory_income_ratio for item in all_households) / max(1, len(all_households)), 6),
            average_unemployment_probability=round(100.0 * sum(item.unemployment_probability for item in all_households) / max(1, len(all_households)), 4),
            average_unemployment_benefit=round(sum(item.last_unemployment_benefit for item in all_households) / max(1, len(all_households)), 4),
            labor_force_participation=round(100.0 * sum(item.employed_by is not None or item.labor_force_participating for item in all_households) / max(1, len(all_households)), 4),
            groups=group_views,
            warning=(
                "Estado HARK sincronizado com emprego/renda do ABM. Risco de desemprego e processo de renda ainda são "
                "hipóteses estruturais não calibradas em microdados reais."
            ),
        )

    labor_market_report = LaborMarketReport(
        benefits_enabled=spec.unemployment_benefits_enabled,
        labor_supply_mode=spec.labor_supply_mode,
        replacement_rate=spec.unemployment_benefit_replacement_rate,
        waiting_months=spec.unemployment_benefit_waiting_months,
        maximum_benefit_months=spec.unemployment_benefit_max_months,
        benefit_cap=spec.unemployment_benefit_cap,
        cumulative_benefits=round(sum(point.unemployment_benefits or 0.0 for point in points), 4),
        final_participation_rate=round(final.labor_force_participation or 0.0, 4),
        average_job_separation_rate=round(sum(point.job_separation_rate or 0.0 for point in points) / max(1, len(points)), 6),
        average_job_finding_rate=round(sum(point.job_finding_rate or 0.0 for point in points) / max(1, len(points)), 6),
        warning=(
            "Benefícios são transferências explícitas do governo e não entram diretamente em G. "
            "A oferta de trabalho v2.4 usa busca e salário de reserva transparentes; não é ainda "
            "uma solução estrutural de utilidade trabalho-lazer calibrada em microdados."
        ),
    )

    result = SimulationResult(
        scenario=spec.name,
        model="economy-zero-labor-benefits-v2.4",
        warning=(
            "Economy Zero é um laboratório estrutural ainda não calibrado com dados reais. "
            "As identidades contábeis são verificadas, mas parâmetros e respostas não devem "
            "ser tratados como previsão econômica."
        ),
        series=points,
        engines=EngineTrace(
            activation=model.activation_runtime.name,
            household_decision=model.consumption_policy.name,
            accounting="economy-lab-sfc-v1.0",
            minsky=(
                "minsky-profile-active-path-v1.0"
                if spec.financial_engine == "minsky_profile" and spec.financial_guidance
                else "minsky-profile-active-static-v1.0"
                if spec.financial_engine == "minsky_profile"
                else "rest-template-bridge"
            ),
            macro=(
                "dynare-7.x-reference-nk-quarterly-v1.0"
                if spec.macro_engine == "dynare" and spec.macro_coupling == "hybrid" and spec.macro_recalibration == "quarterly"
                else "dynare-7.x-reference-nk-hybrid-v1.0"
                if spec.macro_engine == "dynare" and spec.macro_coupling == "hybrid"
                else "dynare-7.x-reference-nk-v1.0"
                if spec.macro_engine == "dynare"
                else "off"
            ),
        ),
        authority=authority_report,
        accounting=accounting,
        banking=banking,
        financial=financial_report,
        household_engine=household_engine_report,
        labor_market=labor_market_report,
        macro=macro_report,
        coupling=coupling_report,
        macro_recalibration=recalibration_report,
        shocks=shock_report,
        summary=SimulationSummary(
            final_gdp_index=final.gdp_index,
            final_inflation=final.inflation,
            final_unemployment=final.unemployment,
            final_corporate_debt=final.corporate_debt or 0.0,
            final_bank_credit=final.bank_credit or 0.0,
            final_gini_wealth=final.gini_wealth or 0.0,
            cumulative_defaults=sum(point.firm_defaults or 0 for point in points),
            ledger_balanced=True,
            final_bank_reserves=final.bank_reserves or 0.0,
            final_central_bank_advances=final.central_bank_advances or 0.0,
            final_government_debt=final.government_debt or 0.0,
            final_private_net_financial_wealth=final.private_net_financial_wealth or 0.0,
            godley_stocks_balanced=stocks.balanced,
            godley_flows_balanced=flows.balanced,
            final_bank_capital=final.bank_capital or 0.0,
            final_bank_capital_ratio=final.bank_capital_ratio or 0.0,
            final_undercapitalized_banks=final.undercapitalized_banks or 0,
            final_interbank_credit=final.interbank_credit or 0.0,
            cumulative_bank_profit_loss=sum(point.bank_profit_loss or 0.0 for point in points),
            cumulative_credit_rationed=sum(point.credit_rationed or 0.0 for point in points),
            cumulative_default_losses=sum(point.default_losses or 0.0 for point in points),
            cumulative_exports=sum(point.exports or 0.0 for point in points),
            cumulative_imports=sum(point.imports or 0.0 for point in points),
            cumulative_net_exports=sum(point.net_exports or 0.0 for point in points),
            final_productive_capital=final.productive_capital or 0.0,
            cumulative_business_investment=sum(point.business_investment or 0.0 for point in points),
            final_household_debt=final.household_debt or 0.0,
            cumulative_household_defaults=sum(point.household_defaults or 0 for point in points),
            cumulative_bank_resolutions=sum(point.bank_resolutions or 0 for point in points),
            cumulative_public_recapitalization=sum(point.public_recapitalization or 0.0 for point in points),
            cumulative_bail_in_losses=sum(point.bail_in_losses or 0.0 for point in points),
            cumulative_unemployment_benefits=sum(point.unemployment_benefits or 0.0 for point in points),
            final_labor_force_participation=final.labor_force_participation or 0.0,
            average_job_separation_rate=sum(point.job_separation_rate or 0.0 for point in points) / max(1, len(points)),
            average_job_finding_rate=sum(point.job_finding_rate or 0.0 for point in points) / max(1, len(points)),
        ),
    )
    if execution_control is not None:
        execution_control.checkpoint(
            "finalized", completed_steps=spec.months, total_steps=spec.months, progress=98.0
        )
    return result


def run_simulation(
    spec: ScenarioSpec,
    execution_control: SimulationExecutionControl | None = None,
) -> SimulationResult:
    if spec.mode == "demo":
        return run_demo_simulation(spec, execution_control=execution_control)
    return run_economy_zero(spec, execution_control=execution_control)
