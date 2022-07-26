import os
import yaml
from pathlib import Path
from algosdk.v2client.algod import AlgodClient

ALGOD_ADDRESS = "https://testnet-algorand.api.purestake.io/ps2"
ALGO_INDEXER_ADDRESS = "https://algoindexer.testnet.algoexplorerapi.io"
ALGOD_TOKEN = "lWrz92T39U4SdqPQHWbZd14QXH94ucTe6Z1biOed"


def getAlgodClient() -> AlgodClient:
    """
    Gets the Algorand node client
    :return: an instance of AlgodClient
    """
    purestake_token = {'X-Api-key': ALGOD_TOKEN}
    return AlgodClient(ALGOD_TOKEN, ALGOD_ADDRESS, headers=purestake_token)


def get_project_root_path() -> Path:
    path = Path(os.path.dirname(__file__))
    return path.parent


def load_config():
    root_path = get_project_root_path()
    config_location = os.path.join(root_path, 'config.yml')

    with open(config_location) as file:
        return yaml.full_load(file)


def get_account_credentials(account_id: int) -> (str, str, str):
    """
    Gets the credentials for the account with number: account_id
    :param account_id: Number of the account for which we want the credentials
    :return: (str, str, str) private key, address and mnemonic
    """
    config = load_config()
    account_name = f"account_{account_id}"
    account = config.get("accounts").get(account_name)
    return account.get("private_key"), account.get("address"), account.get("mnemonic")
