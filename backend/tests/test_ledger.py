import pytest

from economy_lab.finance import Ledger, Posting, UnbalancedTransaction


def test_unbalanced_transaction_is_rejected():
    ledger = Ledger()
    with pytest.raises(UnbalancedTransaction):
        ledger.post(
            tick=1,
            description="bad",
            postings=[Posting("asset:a", 10), Posting("liability:b", -9)],
        )


def test_deposit_transfer_updates_asset_and_bank_liability_mirrors():
    ledger = Ledger()
    ledger.open_instrument_pair(
        tick=0,
        description="A opening",
        asset_account="a:deposit",
        liability_account="bank:deposit:a",
        amount=100,
    )
    ledger.open_instrument_pair(
        tick=0,
        description="B opening",
        asset_account="b:deposit",
        liability_account="bank:deposit:b",
        amount=20,
    )
    paid = ledger.transfer_deposit(
        tick=1,
        description="A pays B",
        source_asset="a:deposit",
        source_bank_liability="bank:deposit:a",
        destination_asset="b:deposit",
        destination_bank_liability="bank:deposit:b",
        amount=30,
    )
    assert paid == 30
    assert ledger.balance("a:deposit") == 70
    assert ledger.balance("b:deposit") == 50
    assert ledger.balance("bank:deposit:a") == -70
    assert ledger.balance("bank:deposit:b") == -50
    ledger.assert_balanced()


def test_bank_loan_creates_matching_credit_and_deposit():
    ledger = Ledger()
    ledger.create_bank_loan(
        tick=1,
        description="loan",
        bank_loan_asset="bank:loan:firm",
        borrower_loan_liability="firm:loan",
        borrower_deposit_asset="firm:deposit",
        bank_deposit_liability="bank:deposit:firm",
        amount=1000,
    )
    assert ledger.balance("bank:loan:firm") == 1000
    assert ledger.balance("firm:loan") == -1000
    assert ledger.balance("firm:deposit") == 1000
    assert ledger.balance("bank:deposit:firm") == -1000
    ledger.assert_balanced()


def test_cross_bank_deposit_transfer_settles_reserves():
    ledger = Ledger()
    ledger.open_instrument_pair(
        tick=0,
        description="A deposit",
        asset_account="a:deposit",
        liability_account="bank:0:deposit_liability:a",
        amount=100,
    )
    ledger.open_instrument_pair(
        tick=0,
        description="B deposit",
        asset_account="b:deposit",
        liability_account="bank:1:deposit_liability:b",
        amount=20,
    )
    ledger.open_instrument_pair(
        tick=0,
        description="Bank 0 reserves",
        asset_account="bank:0:reserve_asset",
        liability_account="central_bank:reserve_liability:bank:0",
        amount=100,
    )
    ledger.open_instrument_pair(
        tick=0,
        description="Bank 1 reserves",
        asset_account="bank:1:reserve_asset",
        liability_account="central_bank:reserve_liability:bank:1",
        amount=20,
    )

    ledger.transfer_deposit(
        tick=1,
        description="A pays B cross-bank",
        source_asset="a:deposit",
        source_bank_liability="bank:0:deposit_liability:a",
        destination_asset="b:deposit",
        destination_bank_liability="bank:1:deposit_liability:b",
        amount=30,
    )

    assert ledger.balance("bank:0:reserve_asset") == 70
    assert ledger.balance("bank:1:reserve_asset") == 50
    assert ledger.balance("central_bank:reserve_liability:bank:0") == -70
    assert ledger.balance("central_bank:reserve_liability:bank:1") == -50
    ledger.assert_balanced()


def test_central_bank_advance_funds_reserve_shortfall():
    ledger = Ledger()
    ledger.open_instrument_pair(
        tick=0,
        description="A deposit",
        asset_account="a:deposit",
        liability_account="bank:0:deposit_liability:a",
        amount=100,
    )
    ledger.open_instrument_pair(
        tick=0,
        description="B deposit",
        asset_account="b:deposit",
        liability_account="bank:1:deposit_liability:b",
        amount=0,
    )
    ledger.open_instrument_pair(
        tick=0,
        description="Bank 0 reserves",
        asset_account="bank:0:reserve_asset",
        liability_account="central_bank:reserve_liability:bank:0",
        amount=10,
    )

    ledger.transfer_deposit(
        tick=1,
        description="Reserve-stressed payment",
        source_asset="a:deposit",
        source_bank_liability="bank:0:deposit_liability:a",
        destination_asset="b:deposit",
        destination_bank_liability="bank:1:deposit_liability:b",
        amount=30,
    )

    # v0.5 funds the payment plus a 10% reserve floor on remaining deposits.
    assert ledger.balance("central_bank:advance_asset:bank:0") == 27
    assert ledger.balance("bank:0:central_bank_borrowing_liability") == -27
    assert ledger.balance("bank:0:reserve_asset") == 7
    assert ledger.balance("bank:1:reserve_asset") == 30
    ledger.assert_balanced()


def test_interbank_market_is_used_before_central_bank_backstop():
    ledger = Ledger()
    ledger.open_instrument_pair(
        tick=0,
        description="A deposit",
        asset_account="a:deposit",
        liability_account="bank:0:deposit_liability:a",
        amount=100,
    )
    ledger.open_instrument_pair(
        tick=0,
        description="B deposit",
        asset_account="b:deposit",
        liability_account="bank:1:deposit_liability:b",
        amount=20,
    )
    ledger.open_instrument_pair(
        tick=0,
        description="Bank 0 reserves",
        asset_account="bank:0:reserve_asset",
        liability_account="central_bank:reserve_liability:bank:0",
        amount=10,
    )
    ledger.open_instrument_pair(
        tick=0,
        description="Bank 1 reserves",
        asset_account="bank:1:reserve_asset",
        liability_account="central_bank:reserve_liability:bank:1",
        amount=100,
    )

    ledger.transfer_deposit(
        tick=1,
        description="A pays B using interbank liquidity",
        source_asset="a:deposit",
        source_bank_liability="bank:0:deposit_liability:a",
        destination_asset="b:deposit",
        destination_bank_liability="bank:1:deposit_liability:b",
        amount=30,
    )

    assert ledger.balance("bank:1:interbank_loan_asset:bank:0") == 27
    assert ledger.balance("bank:0:interbank_borrowing_liability:bank:1") == -27
    assert ledger.balance("central_bank:advance_asset:bank:0") == 0
    assert ledger.balance("bank:0:reserve_asset") == 7
    ledger.assert_balanced()


def test_central_bank_advance_can_be_repaid_from_excess_reserves():
    ledger = Ledger()
    ledger.open_instrument_pair(
        tick=0,
        description="Bank deposits",
        asset_account="customer:deposit",
        liability_account="bank:0:deposit_liability:customer",
        amount=100,
    )
    ledger.open_instrument_pair(
        tick=0,
        description="Bank reserves",
        asset_account="bank:0:reserve_asset",
        liability_account="central_bank:reserve_liability:bank:0",
        amount=30,
    )
    ledger.post(
        tick=0,
        description="Opening CB advance",
        postings=[
            Posting("bank:0:reserve_asset", 20),
            Posting("central_bank:reserve_liability:bank:0", -20),
            Posting("central_bank:advance_asset:bank:0", 20),
            Posting("bank:0:central_bank_borrowing_liability", -20),
        ],
    )

    interest, principal = ledger.service_central_bank_advance(
        tick=1,
        bank_id=0,
        annual_rate=0.0,
        target_reserve_ratio=0.10,
    )
    assert interest == 0
    assert principal == 20
    assert ledger.balance("central_bank:advance_asset:bank:0") == 0
    assert ledger.balance("bank:0:central_bank_borrowing_liability") == 0
    assert ledger.balance("bank:0:reserve_asset") == 30
    ledger.assert_balanced()
