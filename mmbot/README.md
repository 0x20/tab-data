# Intro
The goal of this script is to send a Mattermost message when a transaction is found for that user.

You can subscribe to these messages by adding your Mattermost username (mm_username) to the file `static/members.beancount`

Example:
```
1970-01-01 open Liabilities:Bar:Members:Gust
  mm_name: "gust"
```
This script is called by the Github Actions `.github/workflows/mmbot.yml`. The Action will be triggered for every change in the `ledger/*.beancount` files and will search for the hard-coded commit message "`Automatic commit by backtab`" to assume it is a bar transaction commit.

When a transaction is found the barbot Mattermost account will send a message to the user.

# Development

## Installation

```pip install -r requirements.txt```

or

```nix-shell``` which creates its own virtual environment.
This does require the `nix` package manager.


## Testing

python should be ran from the root dir, so the relative paths are correct.

Show a help text with all switches:

```python mmbot/mmbot-tx.py --help```

Example to show how to test on a beancount file:

```python mmbot/mmbot-tx.py --from_file "./ledger/UberBarmaid_2024-01-18 19:32:39.804552+00:00.beancount"```
