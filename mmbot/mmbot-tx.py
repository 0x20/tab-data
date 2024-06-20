import sys
import logging
import subprocess
import requests
import click
import json
from pprint import pformat
from beancount import loader
from beancount.core.data import Posting as Posting
from beancount.core.data import Transaction as Transaction
from typing import List, Set


class MattermostAPI:
    def __init__(self, server_url, auth_token):
        self.server_url = server_url
        self.api_endpoint = "api/v4/"
        self.auth_token = auth_token
        self.headers = {
            'Authorization': 'Bearer ' + auth_token,
            'Content-Type': 'application/json'
        }

    def mm_view_self(self):
        api_path = "users/me"
        response = requests.get(self.server_url + self.api_endpoint + api_path, headers=self.headers)
        if response.status_code == 200:
            logging.debug('Response mm_view_self:\n %s', pformat(response.json()))
            user = response.json()
            return user['id']
        else:
            logging.error("Error mm_view_self: %s", response.text)

    def mm_search_userid(self, user_name):
        api_path = "users/search"
        data = { "term": user_name }

        response = requests.post(self.server_url + self.api_endpoint + api_path, headers=self.headers, data=json.dumps(data))
        if response.status_code == 200:
            logging.debug('Response mm_search_userid:\n %s', pformat(response.json()))
            user = response.json()
            return user[0]['id']
        else:
            logging.error("Error mm_search_userid: %s", response.text)

    def mm_get_channel_id(self,bot_id,tx_user_id):
        api_path = "channels/direct"
        data = [bot_id, tx_user_id]

        response = requests.post(self.server_url + self.api_endpoint + api_path, headers=self.headers, data=json.dumps(data))
        if response.status_code == 201:
            logging.debug('Response mm_get_channel_id:\n %s', pformat(response.json()))
            channel_id = response.json()
            return channel_id['id']
        else:
            logging.error("Error mm_get_channel_id: %s", response.text)

    def mm_direct_message(self, channel_id, msg):
        api_path = "posts"
        data = {
            "channel_id": channel_id,
            "message": msg
        }
        response = requests.post(self.server_url + self.api_endpoint + api_path, headers=self.headers, data=json.dumps(data))
        if response.status_code == 201:
            logging.debug('Response mm_direct_message:\n %s', pformat(response.json()))
        else:
            logging.error("Error: Failed to post direct message. Status code: %s %s", response.status_code, response.text)


def get_mm_users(users):
    member_names = []
    accounts_to_search = [f"Liabilities:Bar:Members:{member_name}" for member_name in users]
    logging.debug('Users to search: %s', users)
    logging.debug('Accounts to search: %s', accounts_to_search)

    # Load the members data from the 'members.beancount' file
    members_file = "./static/members.beancount"
    with open(members_file, "r") as f:
        members_data = f.read()
    # Parse the members data using beancount
    members_entries, _, _ = loader.load_string(members_data)
    # Find and extract the mm_name for the target member
    mm_name = None
    for member_entry in members_entries:
        if (
            member_entry.__class__.__name__ == "Open" and
            member_entry.account in accounts_to_search or
            member_entry.meta.get("display_name") in users
        ):
            mm_name = member_entry.meta.get("mm_name")
            member_names.append(mm_name)

    if member_names:
        logging.debug('Mattermost user for %s is: %s', users, member_names)
        return member_names
    return None


def get_users_from_tx(tx: Transaction):
    # Extract the member names involved in the transaction
    prefix = "Liabilities:Bar:Members:"
    members: Set[Posting] = set()
    for posting in tx.postings:
        logging.debug(f"Posting: {posting.account}")
        if posting.account.startswith(prefix):
            logging.debug('adding to set')
            members.add(posting.account[len(prefix):].strip())
        logging.debug(f"Members: {members}")
    return list(members)


def extract_added_transactions_from_git_show():
    result = subprocess.run(['git', 'show'], stdout=subprocess.PIPE)
    output = result.stdout.decode('utf-8')
    lines = output.splitlines()
    tx = ""
    for line in lines:
        if line.startswith('+'):
            if line.startswith('++'):
                continue
            tx = tx + line.lstrip('+') + '\n'
    return tx


def get_git_commit_msg():
    """ Check if the commit is a valid backtab transaction """
    result = subprocess.run(['git', 'log', '-1', '--format=%s'], stdout=subprocess.PIPE)
    output = result.stdout.decode('utf-8').rstrip()
    if output != "Automatic commit by backtab":
        logging.debug("Commit msg does not match 'Automatic commit by backtab', assuming not a transaction. Stopping here.")
        return None
    logging.debug('Commit msg: %s', output)
    return output


def parse_transaction(tx: Transaction, users: str) -> str:
    # docs: Transaction(meta, date, flag, payee, narration, tags, links, postings)
    match tx.meta['type']:
        case 'deposit':
            return parse_deposit(tx, users)
        case 'purchase':
            return parse_purchase(tx, users)
        case 'transfer':
            return parse_transfer(tx, users)
        case _:
            return tx.narration


def parse_deposit(txn: Transaction, user: str) -> str:
    """
        Transaction(
        meta={'filename': '<string>', 'lineno': 47, 'timestamp': '2024-06-10 18:04:56.641494', 'type': 'deposit', '__tolerances__': {'EUR': Decimal('0.005')}},
        date=datetime.date(2024, 6, 10), flag='*',
        payee=None,
        narration='Els deposited €42.00',
        tags=frozenset(),
        links=frozenset(),
        postings=[
            Posting(account='Liabilities:Bar:Members:Els', units=-42.00 EUR, cost=None, price=None, flag=None, meta={'filename': '<string>', 'lineno': 50}),
            Posting(account='Assets:Cash:Bar', units=42.00 EUR, cost=None, price=None, flag=None, meta={'filename': '<string>', 'lineno': 51})
        ])
    """
    pretty_message = txn.narration
    return pretty_message


def parse_purchase(txn: Transaction, user: str):
    """
        Transaction(
        meta={'filename': '<string>', 'lineno': 1, 'timestamp': '2024-06-13 21:12:04.521043', 'type': 'purchase', '__tolerances__': {'EUR': Decimal('0.005')}},
        date=datetime.date(2024, 6, 13), flag='*',
        payee=None,
        narration='Miker bought 1 items for €2.50', tags=frozenset(),
        links=frozenset(),
        postings=
        [
        Posting(account='Assets:Inventory:Bar', units=-1 GERMAN, cost=None, price=None, flag=None, meta={'filename': '<string>', 'lineno': 4}),
        Posting(account='Liabilities:Bar:Members:Miker', units=1 GERMAN, cost=None, price=None, flag=None, meta={'filename': '<string>', 'lineno': 5}),
        Posting(account='Liabilities:Bar:Members:Miker', units=2.50 EUR, cost=None, price=None, flag=None, meta={'filename': '<string>', 'lineno': 6}),
        Posting(account='Income:Bar', units=-2.50 EUR, cost=None, price=None, flag=None, meta={'filename': '<string>', 'lineno': 7})])
    """
    # doc: Posting(account, units, cost, price, flag, meta)
    postings: List[Posting] = []
    for posting in txn.postings:
        if posting.account.startswith("Liabilities:Bar:Members:"):
            postings.append(posting)
    assert len(postings) >= 2, "Expecting 2 postings"
    postings = postings[:-1] # remove the last posting which is the total
    pretty_message = f"{txn.narration}:\n"
    for entry in postings:
        pretty_message += f"{entry.units}\n"
    return pretty_message


def parse_transfer(txn: Transaction, user: str):
    return txn.narration


def main_transaction_handling(added_transactions: Transaction, mm_url, token):
    # Get the correct member name from the transaction
    member_names = get_users_from_tx(added_transactions)
    logging.debug('Membernames from transaction: %s', member_names)
    mm_users = get_mm_users(member_names)

    if not mm_users:
        return

    pretty_message = parse_transaction(added_transactions, mm_users)

    if token:
        for mm_user in mm_users:
            logging.debug(f'Sending message {pretty_message} to {mm_user}')
            # Send message via Mattermost API to member
            api = MattermostAPI(mm_url, token)
            # Setup mattermost direct message channel between barbot and transaction user
            barbot_user_id = api.mm_view_self()
            logging.debug('Barbot mm user_id: %s', barbot_user_id)
            tx_user_id = api.mm_search_userid(mm_user)
            logging.debug('%s mm user_id: %s', mm_user, tx_user_id)
            direct_channel_id = api.mm_get_channel_id(barbot_user_id, tx_user_id)
            logging.debug('Direct mm channel id: %s', direct_channel_id)
            # Send mattermost msg
            api.mm_direct_message(direct_channel_id, pretty_message)
            logging.debug('Done.')
    else:
        logging.info('Message: %s', pretty_message)


@click.command()
@click.option('--mm_url', default="https://chat.hackerspace.gent/", required=False, help='Mattermost server URL')
@click.option('--token', required=False, help='Mattermost API token')
@click.option('--from_file', required=False, help='Read a file instead of a git commit')
@click.option('--debug', is_flag=True, help='Enable debug logging')
def main(mm_url, token, from_file, debug):
    """ Send a direct message to the user who made a transaction in the bar """
    logging.basicConfig(format='[%(asctime)s] [%(levelname)s] %(message)s', level='INFO' if not debug else 'DEBUG')
    logging.debug('Starting script %s', __file__)

    if not token:
        logging.warning("No token provided, not sending messages.")

    if from_file:
        with open(from_file, "r") as f:
            added_transactions = f.read()

    else:
        # get the git commit message
        output = get_git_commit_msg()

        # if the last commit is not a backtab transaction, stop here
        if not output:
            sys.exit(1)

        # get transaction from git
        added_transactions = extract_added_transactions_from_git_show()
        logging.debug('Git commit msg:\n %s', added_transactions)


    # Parse the transaction
    tx, _, _ = loader.load_string(added_transactions)
    tx = tx if isinstance(tx, list) else [tx]
    logging.debug(f"There are {len(tx)} transactions")
    for t in tx:
        main_transaction_handling(t, mm_url, token)


if __name__ == '__main__':
    main()
