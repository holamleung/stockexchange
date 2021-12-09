# StockExchange
A virtual stock market platform.

![stockexchange-crop](https://user-images.githubusercontent.com/75563658/142047808-4fd21036-ed94-4bec-ad19-feb93908989f.png)

## Description
```
/stockexchange
 |-helpers.py
 |-README.md
 |-templates
 | |-transfer.html
 | |-sell.html
 | |-login.html
 | |-layout.html
 | |-apology.html
 | |-history.html
 | |-buy.html
 | |-quote.html
 | |-index.html
 | |-register.html
 | |-lookup.html
 |-application.py
 |-stockx.db
 |-static
 | |-styles.css
 |-requirements.txt
 ```
 
## Getting Started
Befor running the web server, we will need an api key to query IEX's data. To do so, follow these steps:

1. Visit iexcloud.io/cloud-login#/register/.
2. Select the “Individual” account type, then enter your email address and a password, and click “Create account”.
3. Once registered, scroll down to “Get started for free” and click “Select Start” to choose the free plan.
4. Once you’ve confirmed your account via a confirmation email, visit https://iexcloud.io/console/tokens.
5. Copy the key that appears under the Token column (it should begin with pk_).
6. In a terminal window execute:
`$ export API_KEY=key`
where `key` is the key token you received
