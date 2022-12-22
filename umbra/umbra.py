import traceback
import json
import sys
try:
    from wakepy import set_keepawake, unset_keepawake
    use_wakepy = True
except NotImplementedError as err:
    traceback.print_exc()
    print("\nYour system does not support using wakepy package. Because of that the program cannot prevent your system from sleeping or getting hibernated, so you have to make extra effort to keep your PC awake during long downloading processes. Please read the error and try to make wakepy work or be careful if you want to start a long downloading process while you are away from your PC.\nContinue running...\n")
    use_wakepy = False
import os
from asyncio import exceptions as ae
from requests import exceptions as re
sys.path.append("./")
sys.dont_write_bytecode = True # Prevent the creation of __pycache__ directories

from helper import Access, Contract, Network
from download_txs import download_txs
from decode_txs_input import decode_txs_input
from get_withdraw_txs import get_withdraw_txs
from get_txs_ens import get_txs_ens
from get_fees import get_fees


_access = Access()
get_ens_a = False
get_w_txs_a = False

try:
    match sys.argv[1]:
        case "mainnet":
            network = Network.MAINNET
        case "polygon":
            network = Network.POLYGON
        case default:
            sys.exit("Incorrect 1. argument! (mainnet, polygon)")

    _access.init_network(network)

    match sys.argv[2]:
        case "umbra":
            fname = f"umbra/data/{_access.network.value}/umbra_contract_txs.json"
            fbackup = f"umbra/data/{_access.network.value}/umbra_contract_txs_BACKUP.json"
            contract_addr = "0xfb2dc580eed955b528407b4d36ffafe3da685401"
            contract = Contract.UMBRA
        case "registry":
            fname = f"umbra/data/{_access.network.value}/stealth_key_registry_contract_txs.json"
            fbackup = f"umbra/data/{_access.network.value}/stealth_key_registry_contract_txs_BACKUP.json"
            contract_addr = "0x31fe56609C65Cd0C510E7125f051D440424D38f3"
            contract = Contract.REGISTRY
        case default:
            sys.exit("Incorrect 2. argument! (umbra, registry)")

    if len(sys.argv) == 4:
        if sys.argv[3] == "ens-a":
            get_ens_a = True
        elif sys.argv[3] == "w_txs-a":
            get_w_txs_a = True
        elif sys.argv[3] == "all":
            get_ens_a = True
            get_w_txs_a = True
        else:
            sys.exit("Incorrect 3. argument! (ens-a, w_txs-a, all)")

except IndexError as err:
    sys.exit("Please give 2 arguments! (1: mainnet, polygon; 2: umbra, registry)")


try:
    # Prevent the OS from sleeping while we run
    if use_wakepy: set_keepawake(keep_screen_awake=False)


    try:
        with open(fname, "r") as file:
            og_data = json.load(file)
            # lb = int(og_data["last_block"])-10 #earlier blocks are definitely unmutable
            lb = int(og_data["last_block"]) + 1

        with open(fbackup, "w") as file:
            json.dump(og_data, file)
            
    except FileNotFoundError as err:
        og_data = {"result": []}
        lb = 0


    print(f"Getting contract transactions from block {lb}...")
    downloaded_data = download_txs(contract_addr, lb)
    downloaded_count = len(downloaded_data)
    print(f"Successfully downloaded {downloaded_count} new transactions.")

    if lb == 0:
        # When we download all the transactions from block 0, we have to delete 1 in case of mainnet
        # and we have to delete 2 in case of polygon from the head of the list.
        _delete = 1 if network == Network.MAINNET else 2
        downloaded_data = downloaded_data[_delete:]

    # If the API endpoint timeouts...
    while True:
        try:
            """
            We don't want to concat og_data and downloaded_data yet,
            so there is less data to check against "last_..." in the called methods.
            """
            get_fees(og_data, downloaded_data)

            if contract == Contract.UMBRA:
                decode_txs_input(contract_addr, og_data, downloaded_data)

                get_withdraw_txs(og_data, downloaded_data, get_w_txs_a)

            if network == Network.MAINNET:
                get_txs_ens(og_data, downloaded_data, contract, get_ens_a)

            break

        except (ae.TimeoutError, re.ConnectTimeout, re.ConnectionError) as err:
            print(f"\nRestarting because of {err}\n")

        finally:
            og_data["result"] = [*og_data["result"], *downloaded_data]
            og_data["last_block"] = og_data["result"][-1]["blockNumber"]
            # If an error occures we need to empty this list so the methods won't enrich the downloaded data more times.
            downloaded_data = []


except KeyboardInterrupt:
    print("\nmanually interrupted.\n")

finally:
    with open(fname, "w") as file:
        json.dump(og_data, file)

    trx_count = len(og_data["result"])
    print(f"\n{trx_count} txs have been written into the file.")

    # Renable OS sleeping
    if use_wakepy: unset_keepawake()
