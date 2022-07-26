from pyteal import *


def approval_program():
    # Asset Info
    asset_id_key = Bytes("aid")
    asset_price_key = Bytes("ap")

    # Fee Receiver
    fee_receiver_key = Bytes("fr")
    fee_percent_key = Bytes("fp")

    # APP State
    app_state = Bytes("as")

    # Variables
    # Every internal transaction costs 1_000
    # Minimum balance held in escrow 200_000
    transactions_count = 5
    escrow_min_balance = Int(200_000 + (1_000 * transactions_count))

    # APP States Enum
    STATUS_NOT_INIT = Int(0)
    STATUS_ACTIVE = Int(1)
    STATUS_IN_PROGRESS = Int(2)

    @Subroutine(TealType.none)
    def sendAssetTo(assetID: Expr, account: Expr, amount: Expr) -> Expr:
        asset_holding = AssetHolding.balance(
            Global.current_application_address(), assetID
        )
        return Seq(
            asset_holding,
            If(
                And(
                    asset_holding.hasValue(),
                    asset_holding.value() >= amount
                )
            ).Then(
                Seq(
                    InnerTxnBuilder.Begin(),
                    InnerTxnBuilder.SetFields(
                        {
                            TxnField.type_enum: TxnType.AssetTransfer,
                            TxnField.xfer_asset: assetID,
                            TxnField.asset_receiver: account,
                            TxnField.asset_amount: amount
                        }
                    ),
                    InnerTxnBuilder.Submit(),
                )
            ),
        )

    @Subroutine(TealType.none)
    def sendPaymentTo(account: Expr, amount: Expr) -> Expr:
        return Seq(
            If(Balance(Global.current_application_address()) >= amount).Then(
                Seq(
                    InnerTxnBuilder.Begin(),
                    InnerTxnBuilder.SetFields(
                        {
                            TxnField.type_enum: TxnType.Payment,
                            TxnField.receiver: account,
                            TxnField.amount: amount
                        }
                    ),
                    InnerTxnBuilder.Submit(),
                )
            ),
        )

    @Subroutine(TealType.none)
    def closeAssetTo(assetID: Expr, account: Expr) -> Expr:
        asset_holding = AssetHolding.balance(
            Global.current_application_address(), assetID
        )
        return Seq(
            asset_holding,
            If(asset_holding.hasValue()).Then(
                Seq(
                    InnerTxnBuilder.Begin(),
                    InnerTxnBuilder.SetFields(
                        {
                            TxnField.type_enum: TxnType.AssetTransfer,
                            TxnField.xfer_asset: assetID,
                            TxnField.asset_close_to: account,
                        }
                    ),
                    InnerTxnBuilder.Submit(),
                )
            ),
        )

    @Subroutine(TealType.none)
    def closeAccountTo(account: Expr) -> Expr:
        return If(Balance(Global.current_application_address()) != Int(0)).Then(
            Seq(
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields(
                    {
                        TxnField.type_enum: TxnType.Payment,
                        TxnField.close_remainder_to: account,
                    }
                ),
                InnerTxnBuilder.Submit(),
            )
        )

    # Create Application Function
    on_create = Seq(
        Assert(Txn.application_args.length() == Int(3)),
        App.globalPut(app_state, STATUS_NOT_INIT),
        App.globalPut(asset_id_key, Btoi(Txn.application_args[0])),
        App.globalPut(fee_receiver_key, Txn.application_args[1]),
        App.globalPut(fee_percent_key, Btoi(Txn.application_args[2])),
        Assert(
            And(
                # ensure that the fee percent is between 0 and 100
                App.globalGet(fee_percent_key) >= Int(0),
                App.globalGet(fee_percent_key) <= Int(100),
            )
        ),
        Approve()
    )

    # On Setup Function
    # Transaction Group:
    # [1] Payment for escrow account
    # [2] Application call - on_setup
    #     - [1] sale_price: bigint
    # [3] Transfer of Asset
    tx_index_current = Txn.group_index()
    tx_index_escrow_payment = tx_index_current - Int(1)
    tx_index_asset_transfer = tx_index_current + Int(1)
    on_setup = Seq(
        Assert(
            And(
                # Match group txn size
                Global.group_size() == Int(3),

                # Check if status is active or in progress
                Or(
                    App.globalGet(app_state) != STATUS_IN_PROGRESS,
                ),

                # Check if the first transaction is an escrow payment
                Gtxn[tx_index_escrow_payment].type_enum() == TxnType.Payment,

                # Check if the escrow payment is sent by the creator address
                Gtxn[tx_index_escrow_payment].sender() == Global.creator_address(),

                # Check if the escrow payment is sent to the escrow wallet
                Gtxn[tx_index_escrow_payment].receiver() == Global.current_application_address(),

                # Check if the escrow payment balance matches the minimum balance required
                Gtxn[tx_index_escrow_payment].amount() == escrow_min_balance,

                # Check if the final transaction is an asset transfer transaction
                Gtxn[tx_index_asset_transfer].type_enum() == TxnType.AssetTransfer,

                # Check if the asset is being sent by the creator
                Gtxn[tx_index_asset_transfer].sender() == Global.creator_address(),

                # Check if the asset is being received by the escrow address
                Gtxn[tx_index_asset_transfer].asset_receiver() == Global.current_application_address(),

                # Check if the asset transferred is more than 1
                Gtxn[tx_index_asset_transfer].asset_amount() >= Int(1),

                # Check if the asset transferred is the same as designated type
                Gtxn[tx_index_asset_transfer].xfer_asset() == App.globalGet(asset_id_key),
            )
        ),
        # Set the asset price and status to is selling
        App.globalPut(asset_price_key, Btoi(Txn.application_args[1])),
        App.globalPut(app_state, STATUS_IN_PROGRESS),

        # opt into NFT asset -- because you can't opt in if you're already opted in, this is what
        # we'll use to make sure the contract has been set up
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: App.globalGet(asset_id_key),
                TxnField.asset_receiver: Global.current_application_address(),
            }
        ),
        InnerTxnBuilder.Submit(),
        Approve(),
    )

    # Buy Asset from escrow
    # Transaction Group:
    # [1] Maybe Optin ?
    # [2] Transfer of funds
    # [3] Application call - on_buy
    tx_index_buy = Txn.group_index() - Int(1)

    # @var NFT Balance
    asset_balance = AssetHolding.balance(
        Global.current_application_address(),
        App.globalGet(asset_id_key)
    )
    # @var is buyer opted in to the asset
    buyer_asset_balance = AssetHolding.balance(
        Txn.sender(), App.globalGet(asset_id_key)
    )
    # The requested amount of the asset
    asset_amount = Btoi(Txn.application_args[1])
    on_buy = Seq(
        asset_balance,
        buyer_asset_balance,
        Assert(
            And(
                # Check if escrow has asset balance
                asset_balance.hasValue(),
                asset_balance.value() >= asset_amount,

                # Check if status is initialized and ready to sell
                App.globalGet(app_state) == STATUS_IN_PROGRESS,

                # ensure the buyer is opted-in to the NFT
                buyer_asset_balance.hasValue(),

                # Check if the purchase payment is valid
                And(
                    Gtxn[tx_index_buy].type_enum() == TxnType.Payment,
                    Gtxn[tx_index_buy].sender() == Txn.sender(),
                    Gtxn[tx_index_buy].receiver() == Global.current_application_address(),
                    Gtxn[tx_index_buy].amount() == App.globalGet(asset_price_key) * asset_amount,
                ),
            )
        ),
        # Set the status as not selling
        App.globalPut(app_state, STATUS_ACTIVE),

        # send the asset to the buyer
        sendAssetTo(App.globalGet(asset_id_key), Gtxn[tx_index_buy].sender(), asset_amount),

        # send the fee to the fee receiver
        sendPaymentTo(
            App.globalGet(fee_receiver_key),
            (
                (
                    App.globalGet(fee_percent_key)
                    * (App.globalGet(asset_price_key) * asset_amount)
                ) / Int(100)
            )
        ),

        Approve(),
    )

    # Define method and method handler
    handle_noop_method = Txn.application_args[0]
    handle_noop = Cond(
        [handle_noop_method == Bytes("on_setup"), on_setup],
        [handle_noop_method == Bytes("on_buy"), on_buy],
    )

    # Delete app and return the funds
    handle_deleteapp = Seq(
        Assert(
            Or(
                # Transaction sender must be the creator if status is in progress
                And(
                    App.globalGet(app_state) == STATUS_IN_PROGRESS,
                    Txn.sender() == Global.creator_address()
                ),
                # Or transaction sender maybe anyone if status is not in progress
                And(
                    App.globalGet(app_state) != STATUS_IN_PROGRESS
                )
            )
        ),

        # send the asset to the creator
        closeAssetTo(App.globalGet(asset_id_key), Global.creator_address()),

        # send the remainder of funds back to the creator
        closeAccountTo(Global.creator_address()),

        Approve(),
    )

    # Handle Opt-in function
    handle_optin = Reject()
    handle_closeout = Reject()
    handle_updateapp = Reject()

    program = Cond(
        [Txn.application_id() == Int(0), on_create],
        [Txn.on_completion() == OnComplete.NoOp, handle_noop],
        [Txn.on_completion() == OnComplete.OptIn, handle_optin],
        [Txn.on_completion() == OnComplete.CloseOut, handle_closeout],
        [Txn.on_completion() == OnComplete.UpdateApplication, handle_updateapp],
        [Txn.on_completion() == OnComplete.DeleteApplication, handle_deleteapp],
    )

    return program


def clear_state_program():
    print("Clear Program")
    return Approve()


if __name__ == "__main__":
    with open("compiled/escrow_approval.teal", "w") as f:
        compiled = compileTeal(approval_program(), mode=Mode.Application, version=5)
        f.write(compiled)

    with open("compiled/escrow_clear_state.teal", "w") as f:
        compiled = compileTeal(clear_state_program(), mode=Mode.Application, version=5)
        f.write(compiled)
