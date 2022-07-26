from algosdk import encoding
from algosdk.future import transaction
from algosdk.logic import get_application_address
from algosdk.v2client.algod import AlgodClient

from contracts import __version__
from contracts.auction import approval_program, clear_state_program
from utils.account import Account
from utils.helper import fullyCompileContract, waitForTransaction

# Global program
APPROVAL_PROGRAM = b''
CLEAR_STATE_PROGRAM = b''


def test_version():
    assert __version__ == '0.1.0'


def getContracts(client: AlgodClient) -> [bytes, bytes]:
    """Get the compiled TEAL contracts for the auction.
    Args:
        client: An algod client that has the ability to compile TEAL programs.
    Returns:
        A tuple of 2 byte strings. The first is the approval program, and the
        second is the clear state program.
    """
    global APPROVAL_PROGRAM
    global CLEAR_STATE_PROGRAM

    if len(APPROVAL_PROGRAM) == 0:
        APPROVAL_PROGRAM = fullyCompileContract(client, approval_program())
        CLEAR_STATE_PROGRAM = fullyCompileContract(client, clear_state_program())

    return APPROVAL_PROGRAM, CLEAR_STATE_PROGRAM


def createApp(
    client: AlgodClient,
    sender: Account,
    seller: str,
    assetID: int,
    startTime: int,
    endTime: int,
    reserve: int,
    minBidIncrement: int,
) -> int:
    """Create a new escrow.
    Args:
        client: An algod client.
        sender: The account that will create the auction application.
        seller: The address of the seller that currently holds the NFT being
            auctioned.
        assetID: The ID of the NFT being auctioned.
        startTime: A UNIX timestamp representing the start time of the auction.
            This must be greater than the current UNIX timestamp.
        endTime: A UNIX timestamp representing the end time of the auction. This
            must be greater than startTime.
        reserve: The reserve amount of the auction. If the auction ends without
            a bid that is equal to or greater than this amount, the auction will
            fail, meaning the bid amount will be refunded to the lead bidder and
            the NFT will return to the seller.
        minBidIncrement: The minimum different required between a new bid and
            the current leading bid.
    Returns:
        The ID of the newly created auction app.
    """
    approval, clear = getContracts(client)

    globalSchema = transaction.StateSchema(num_uints=7, num_byte_slices=2)
    localSchema = transaction.StateSchema(num_uints=0, num_byte_slices=0)

    fee = 1

    app_args = [
        encoding.decode_address(seller),
        assetID.to_bytes(8, "big"),
        startTime.to_bytes(8, "big"),
        endTime.to_bytes(8, "big"),
        reserve.to_bytes(8, "big"),
        minBidIncrement.to_bytes(8, "big"),
        fee.to_bytes(8, "big")
    ]

    txn = transaction.ApplicationCreateTxn(
        sender=sender.getAddress(),
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=approval,
        clear_program=clear,
        global_schema=globalSchema,
        local_schema=localSchema,
        app_args=app_args,
        sp=client.suggested_params(),
    )

    signedTxn = txn.sign(sender.getPrivateKey())

    client.send_transaction(signedTxn)

    response = waitForTransaction(client, signedTxn.get_txid())
    assert response.applicationIndex is not None and response.applicationIndex > 0
    return response.applicationIndex


def setupApp(
    client: AlgodClient,
    appID: int,
    funder: Account,
    nftHolder: Account,
    nftID: int,
    nftAmount: int,
) -> None:
    """Finish setting up an auction.
    This operation funds the app auction escrow account, opts that account into
    the NFT, and sends the NFT to the escrow account, all in one atomic
    transaction group. The auction must not have started yet.
    The escrow account requires a total of 0.203 Algos for funding. See the code
    below for a breakdown of this amount.
    Args:
        client: An algod client.
        appID: The app ID of the auction.
        funder: The account providing the funding for the escrow account.
        nftHolder: The account holding the NFT.
        nftID: The NFT ID.
        nftAmount: The NFT amount being auctioned. Some NFTs has a total supply
            of 1, while others are fractional NFTs with a greater total supply,
            so use a value that makes sense for the NFT being auctioned.
    """
    appAddr = get_application_address(appID)

    suggestedParams = client.suggested_params()

    fundingAmount = (
        # min account balance
        100_000
        # additional min balance to opt into NFT
        + 100_000
        # 4 * min txn fee
        + 4 * 1_000
    )
    print("fundingAmount " + fundingAmount.__str__())

    fundAppTxn = transaction.PaymentTxn(
        sender=funder.getAddress(),
        receiver=appAddr,
        amt=fundingAmount,
        sp=suggestedParams,
    )
    print("fundAppTxn " + fundAppTxn.__str__())

    setupTxn = transaction.ApplicationCallTxn(
        sender=funder.getAddress(),
        index=appID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[b"setup"],
        foreign_assets=[nftID],
        sp=suggestedParams,
    )
    print("setupTxn " + setupTxn.__str__())

    fundNftTxn = transaction.AssetTransferTxn(
        sender=nftHolder.getAddress(),
        receiver=appAddr,
        index=nftID,
        amt=nftAmount,
        sp=suggestedParams,
    )
    print("fundNftTxn " + fundNftTxn.__str__())

    transaction.assign_group_id([fundAppTxn, setupTxn, fundNftTxn])

    signedFundAppTxn = fundAppTxn.sign(funder.getPrivateKey())
    signedSetupTxn = setupTxn.sign(funder.getPrivateKey())
    signedFundNftTxn = fundNftTxn.sign(nftHolder.getPrivateKey())

    client.send_transactions([signedFundAppTxn, signedSetupTxn, signedFundNftTxn])

    waitForTransaction(client, signedFundAppTxn.get_txid())

