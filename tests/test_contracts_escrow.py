import base64

from algosdk import encoding
from algosdk.logic import get_application_address

from contracts import __version__
from tests.helper_escrow import getContracts, createApp, setupApp, placeOrder
from utils.account import Account
from utils.helper import getAppGlobalState, createDummyAsset, getBalances
from utils.setup import getAlgodClient, get_account_credentials


def test_contract_compile():
    """
    Compile, setup and test teal contracts
    :return: teal contract bytes
    """
    client = getAlgodClient()
    approval, clear = getContracts(client)

    print('--- Approval ---')
    print(base64.b64encode(approval))

    print('--- Clear ---')
    print(base64.b64encode(clear))

    assert approval is not b'' and clear is not b''


# def test_create():
#     client = getAlgodClient()
#
#     creator_pk, creator_a, creator_m = get_account_credentials(1)
#
#     # Create a dummy asset
#     assetID = createDummyAsset(client, 1, Account(creator_pk))
#
#     appID = createApp(
#         client=client,
#         creator=Account(creator_pk),
#         assetID=assetID,
#     )
#
#     actual = getAppGlobalState(client, appID)
#     expected = {
#         b"as": 0,
#         b"aid": assetID,
#     }
#
#     assert actual == expected
#
# def test_setup():
#     client = getAlgodClient()
#
#     creator_pk, creator_a, creator_m = get_account_credentials(1)
#
#     # 10 Algo
#     assetAmount = 1
#     assetID = createDummyAsset(client, 1, Account(creator_pk))
#     assetPrice = 1_000_000 * 10
#
#     appID = createApp(
#         client=client,
#         creator=Account(creator_pk),
#         assetID=assetID,
#     )
#
#     setupApp(
#         client=client,
#         appID=appID,
#         funder=Account(creator_pk),
#         assetID=assetID,
#         assetPrice=assetPrice,
#     )
#
#     actualState = getAppGlobalState(client, appID)
#     expectedState = {
#         b"as": 2,
#         b"aid": assetID,
#         b"ap": assetPrice,
#     }
#
#     assert actualState == expectedState
#
#     actualBalances = getBalances(client, get_application_address(appID))
#     expectedBalances = {0: 2 * 100_000 + 3 * 1_000, assetID: assetAmount}
#
#     assert actualBalances == expectedBalances

def test_buy():
    client = getAlgodClient()

    creator_pk, creator_a, creator_m = get_account_credentials(1)
    buyer_pk, buyer_a, buyer_m = get_account_credentials(2)

    # 10 Algo
    assetID = createDummyAsset(client, 1, Account(creator_pk))
    assetPrice = 1_000_000 * 1

    feeReceiver = 'DPANDA7MC3CHRPXCORO4YBB56NKKCEEMREWO6VW2WT2NYXSADUTBRZCXWU'
    feePercent = 5

    appID = createApp(
        client=client,
        creator=Account(creator_pk),
        assetID=assetID,
    )

    setupApp(
        client=client,
        appID=appID,
        funder=Account(creator_pk),
        assetID=assetID,
        assetPrice=assetPrice,
    )

    actualState = getAppGlobalState(client, appID)
    expectedState = {
        b"as": 2,
        b"aid": assetID,
        b"ap": assetPrice,
        b"fr": encoding.decode_address(feeReceiver),
        b"fp": feePercent
    }

    assert actualState == expectedState

    placeOrder(
        client=client,
        appID=appID,
        buyer=Account(buyer_pk),
        assetID=assetID,
        assetPrice=assetPrice
    )

    actualBalances = getBalances(client, get_application_address(appID))
    expectedBalances = {0: 0}

    assert actualBalances == expectedBalances


def test_version():
    assert __version__ == '0.1.0'
