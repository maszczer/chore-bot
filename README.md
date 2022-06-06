# chore-bot
Household chore rotation assignment and completion tracking bot. Run this on a machine that is always on, such as a Raspberry Pi.

# Dependancies
* google-api-python-client 
* google-auth-httplib2 
* google-auth-oauthlib

# Setup
To run the chore bot, you must create the following files in the root directory of the cloned repo:
* `config.json`
* `credentials.json`
* `token.json`
* `people.csv`
* `chores.csv`
* `state.txt`

If `token.json` is not provided, one will be created automatically, but the user will need to interact with the Google oauth consent screen during the first time the program is run.

To begin the program, set `run_chorebot.py` to be called by a Python 3 interpreter on boot by the host machine. `cron` is the recommended method. Then, reboot the host machine. 
The admin defined in `config.json` will receive an email stating that the program has started.

## config.json
Copy the contents of `config_template.json` into a new file called `config.json` and populate the fields. The admin is an account that will receive extra emails for startup and fatal errors.

## credentials.json
This is a Google OAuth 2.0 Client ID, obtained by downloading the file from the Google Cloud console for a project associated with the email address to be used by the bot.
The file can be generated under "APIs & Services" > "Credentials".
See [Google's documentation](https://developers.google.com/workspace/guides/get-started) for more information on how to set up a project and generate OAuth credentials.

## token.json
Google authentication token file. 
If `token.json` is not provided, one will be created automatically, but the user will need to interact with the Google oauth consent screen during the first time the program is run.
Thus, for headless applications, providing a pre-generated token is useful.

## people.csv
A CSV file representing the different people in the chore rotation.
One row represents one person.
Columnwise format must be: \<name\>,\<email_address\>,\<group_id\>

## chores.csv
A CSV file representing the chores in the rotation. One row represents one chore.
Columnwise format must be: \<chore_name\>,\<group_id\>
  
## state.txt
A txt file with one number per line. This file tracks the rotation states of the chore groups and the time at which the last chores were issued.
This enables consistancy across reboots.
The first line is the unix time at which the last set of chores was issued. `0` is an acceptable initial value. 
All following lines are rotation indices for each of the rotation groups. There must be at least one of these, since there must always be a common group. 
`0` is an acceptable initial value.
