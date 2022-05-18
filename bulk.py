import erdpy, logging, json, os, binascii, subprocess, base64, configparser

from argparse import ArgumentParser
from erdpy import utils, config
from erdpy.accounts import Account, Address
from erdpy.proxy import ElrondProxy
from erdpy.transactions import BunchOfTransactions

logging.basicConfig(level=logging.DEBUG, filename='app.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s')

###################################   INIT   ##################################################################

#made config file for ease of use
config = configparser.RawConfigParser()
config.read('config.cfg')

global_config_dictionary = dict(config.items('GLOBAL'))
deploy_config_dictionary = ""

#This will create a production version or devnet version - #False = development, True = production
if global_config_dictionary['deploy_to'] == "p":
    deploy_config_dictionary = dict(config.items('PRODUCTION'))
elif global_config_dictionary['deploy_to'] == "t":
    deploy_config_dictionary = dict(config.items('TEST'))
else:
    deploy_config_dictionary = dict(config.items('DEVELOPMENT'))


###################################   INIT   ##################################################################

ONE_EGLD_STR = "1" + "0" * 18
ONE_EGLD = int(ONE_EGLD_STR)
GAS_PRICE = 1000000000
#transaction request sze is limited because of the HTTP post size
TRANSACTION_REQUEST_SIZE = 100


def main():

    if int(global_config_dictionary['deploy_whitelist']) == 1:
        create_whitelist()

    if int(global_config_dictionary['deploy_nft']) == 1:
        bulk_mint()    


def bulk_mint():

    #base cid for pics at nft.storage
    base_cid = deploy_config_dictionary['base_cid']

    #base uri for pics at nft.storage
    base_uri = deploy_config_dictionary['base_uri']

    # needs to be the hex version of the number 1000 which is 10% [and not the hex vesion os ASCII 1000]
    royalties = deploy_config_dictionary['royalties']

    # needs to be the hex version of the number 050000000000000000 which is .5 egld [and not the hex vesion os ASCII 050000000000000000]
    selling_price = deploy_config_dictionary['selling_price']

    # json metadata file
    json_path = deploy_config_dictionary['json_path']

    #get the file object 
    json_metadata_file = open(json_path,mode='r')

    #read all of the lines
    json_metadata = json_metadata_file.read()

    #close the file
    json_metadata_file.close()

    # parse json metadata:
    metadata_dictionary = json.loads(json_metadata)

    #payload counter
    dictionary_count = len(metadata_dictionary)

    #build the payload
    https_url = "https://" + base_cid + "/" + base_uri + "/"

    #transaction counters
    cost = 0
    transaction_counter = 0
    transaction_batch_counter = 0
  
    # get the transaction_bunch
    bunch = transaction_bunch()

    while transaction_counter < dictionary_count:

        #nft_token = token_name.encode('utf-8').hex()
        nft_name = metadata_dictionary[transaction_counter]["name"].encode('utf-8').hex()
        #nft_uri = (https_url + metadata_dictionary[transaction_counter]["image"]).encode('utf-8').hex()
        nft_uri = ("[" + https_url + metadata_dictionary[transaction_counter]["image"] + ", " + https_url + str(transaction_counter)+ ".json]").encode('utf-8').hex()

        #get attributes dictionary into a string
        attribute_count = len(metadata_dictionary[transaction_counter]["attributes"])
        attribute_counter = 0

        attributes_raw = "tags:"

        while attribute_counter < attribute_count:
            attributes_raw += metadata_dictionary[transaction_counter]["attributes"][attribute_counter]["trait_type"] + ","  + metadata_dictionary[transaction_counter]["attributes"][attribute_counter]["value"] + ","
            attribute_counter += 1

        # don't understand the CID / Metadata yet - it is undocumented and no one in dev knows the standard
        # most people believe there is not a standard for metadata. This may or may not have an effect on the NFT explorer
        # displaying data on chain - for now just sending in attributes and a url.
        #nft_attributes = (attributes_raw[:-1] + ";metadata:" + base_cid + "/" + metadata_dictionary[transaction_counter]["image"]).encode('utf-8').hex()
    
        nft_attributes = attributes_raw[:-1].encode('utf-8').hex()
        
        nft_hash = metadata_dictionary[transaction_counter]["dna"].encode('utf-8').hex()
        nft_royalties = hex(int(deploy_config_dictionary['royalties'])).lstrip("0x").rstrip("L")
        nft_selling_price = hex(int(deploy_config_dictionary['selling_price'])).lstrip("0x").rstrip("L")

        nft_royalties = f"{int(deploy_config_dictionary['royalties']):X}".zfill(16)
        nft_selling_price = f"{int(deploy_config_dictionary['selling_price']):X}".zfill(16)

        #nft name, nft uri, image, attributes, hash, royalties, selling price, token, payment nonce - @ with no value is null
        data = "createNFT@" + nft_name + "@" + nft_uri + "@@" + nft_attributes + "@" + nft_hash + "@" + nft_royalties + "@" + nft_selling_price + "@@"
    
        logging.debug(metadata_dictionary[transaction_counter]["name"])

        bunch.add(data)

        transaction_batch_counter += 1

        transaction_counter += 1

        #limit the transaction batch size
        if transaction_batch_counter == TRANSACTION_REQUEST_SIZE:
            transaction_batch_counter = 0
            num_txs, _ = bunch.send()
            bunch = transaction_bunch()
            print("Sent", transaction_counter, " mint transaction(s).")

    if transaction_batch_counter > 0:
        #send the remaining transactions
        num_txs, _ = bunch.send()
        bunch = transaction_bunch()
        print("Sent", transaction_counter, "mint transaction(s).")

def create_whitelist():

	# update updateBuyerWhitelistCheck to true (1)
    whitelistEnableData = str("updateBuyerWhitelistCheck@01")
    bunch = transaction_bunch()
    bunch.add(whitelistEnableData)
    num_txs, _ = bunch.send()
    print("Sent updateBuyerWhitelistCheck@01 to enable whitelist.")

    # file path for the whitelist
    whitelist_path = deploy_config_dictionary['whitelist_path']
    whitelist_bech32_file_name = whitelist_path.replace(".txt", "") + "-bech32.txt"

    # get the whitelist file contents
    whitelist_file = open(whitelist_path,'r') # read only mode
    
    if int(global_config_dictionary['recreate_bech32']) == 1:
    
        #open the bech file and close and it will save blank
        whitelist_bech32_file = open(whitelist_bech32_file_name,'w') 
        whitelist_bech32_file.close()

        #convert addresses to bech32
        for text_line in whitelist_file.readlines(): 
            os.system('erdpy wallet bech32 --decode ' + text_line.replace('\n', '') + ' >> ' + whitelist_bech32_file_name)
            print("Completed bech32 decode for address " + text_line)

    whitelist_file.close()

    #open the bech file finally generate the whitelist
    whitelist_bech32_file = open(whitelist_bech32_file_name,'r') # read only mode

    #transaction counters
    cost = 0
    transaction_counter = 0
    transaction_batch_counter = 0

    # get the transaction_bunch
    bunch = transaction_bunch()

    #send the commande to the contract
    for text_line in whitelist_bech32_file.readlines():    
        
        buyer_count = "00" # 0
        buyer_limit = "01" # 1
        bech32_address = str(text_line).replace('\n', '')
        
        data = str("createBuyerAddress@" + buyer_count + "@" + buyer_limit + "@" + bech32_address)
        
        logging.debug(bech32_address)

        bunch.add(data)

        transaction_counter += 1
        transaction_batch_counter += 1
    
        #limit the transaction batch size
        if transaction_batch_counter == TRANSACTION_REQUEST_SIZE:
            transaction_batch_counter = 0
            num_txs, _ = bunch.send()
            bunch = transaction_bunch()
            print("Sent", transaction_counter, " whitelist transaction(s).")

    num_txs, _ = bunch.send()
    bunch = transaction_bunch()
    print("Sent", transaction_counter, "whitelist transaction(s).")

    # close the file handle
    whitelist_bech32_file.close()

    #remove the temp bech32 file - remove after a bit. Leave the file in case a re-run is needed
    #os.remove(whitelist_bech32_file_name)


class transaction_bunch:

    # FYI - The HTTP POST can not be larger then standard limits. Send 100 per request for now
        
    #contract address to deploy to
    contract_address = deploy_config_dictionary['contract_address']

    # wallet file for deployment
    pem = deploy_config_dictionary['pem']

    # proxy address for elrond
    proxy_address = deploy_config_dictionary['proxy_address']

    # chain id for elrond 
    chain_id = deploy_config_dictionary['chain'] 

    #payload counters
    transaction_counter = 0
    transaction_batch_counter = 0
    tx_version = 1
    options = ""    
    value = "0"

    # The init method or constructor
    def __init__(self):
        self.parser = ArgumentParser()
        self.parser.add_argument("--proxy", default=self.proxy_address)
        self.parser.add_argument("--pem", default=self.pem)
        self.args = self.parser.parse_args()
        self.proxy = ElrondProxy(self.args.proxy)
        self.sender = Account(pem_file=self.args.pem)
        self.sender.sync_nonce(self.proxy)
        self.bunch = BunchOfTransactions()

    # adds an item to the bunch
    def add(self, data): 

		#seems to be a moving target and mystery. I used 20MM for a while
        gas_limit = 50000 + len(data) * 200000

        #bunch.add(sender, address.bech32(), sender.nonce, str(value), data, GAS_PRICE, gas_limit, chain_id, tx_version, options)
        self.bunch.add(self.sender, Address(self.contract_address).bech32(), self.sender.nonce, self.value, data, GAS_PRICE, gas_limit, self.chain_id, self.tx_version, self.options)
        self.sender.nonce += 1

    # send the bunch    
    def send(self):    
        return self.bunch.send(self.proxy)   


if __name__ == "__main__":
    main()