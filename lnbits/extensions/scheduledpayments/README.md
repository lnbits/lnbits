# Scheduled Payments

## Schedule recurring payments in the future.

## Usage

1. Create a schedule by clicking "NEW SCHEDULE"

2. Fill in the options for your Schedule
	- Select a wallet
	- Select a currency
	- Enter an amount in the selected currency
	- Enter a LNURL or Lightning Address (i.e. LNURLxxxxxxxxxx or username@domain.com)
	- Enter an interval
		- This is a `cron expression`. It is a very powerful way of expressing time conditions, but can be a bit tricky!
		- You can click "See common options" and select from a list of common choices.
		- You can visit [https://crontab.guru/examples.html](Crontab Guru) to see a list of even more choices!
	- Select a timezone
	- (optional) Select a Start Date
		- The schedule will start at 12:00:00 AM on the date selected
	- (optional) Select an End Date
		- The schedule will stop at 12:00:00 AM on the date selected

3. Click "Create Scheduled Payments"

4. Your schedule will now run. You can view its status in the "Schedule Event History" section. This section will show a status of "in_progress", "complete" or "Error: {error message}". If it looks like a schedule is stuck "in_progress", it will automatically time out after 5 minutes.