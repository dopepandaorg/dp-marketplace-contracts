from algosdk.v2client.algod import AlgodClient
from utils.setup import getAlgodClient


def test_getAlgodClient():
    client = getAlgodClient()
    assert isinstance(client, AlgodClient)

    response = client.health()
    assert response is None