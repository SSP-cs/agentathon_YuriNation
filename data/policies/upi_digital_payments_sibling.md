# Nova Business UPI Payments Governance Policy

## 1. UPI Transaction Ceilings and Frequency Thresholds
Nova Bank serves as a Payment Service Provider (PSP) and Issuer Bank on the Unified Payments Interface (UPI) network in compliance with NPCI and RBI regulations.

* **Standard Peer-to-Peer (P2P) Daily Limit**: Business account holders are subject to a cumulative transfer cap of INR 2,00,000 per 48-hour rolling window.
* **Transaction Count Limit**: A ceiling of 35 UPI outbound debit transactions is imposed within any consecutive 48-hour window across all UPI third-party app handles linked to the account.
* **High-Value Verified Merchant Category Codes (MCC)**: The daily cap is extended to INR 12,00,000 per 48 hours exclusively for designated merchant categories:
  - Hospitals and healthcare institutions (MCC 8062, 8011)
  - Educational universities and examination fees (MCC 8220, 8211)
  - Capital market initial public offerings (IPO) and government treasury bonds via UPI ASBA.

## 2. Onboarding Cooling-Off Period for New Devices and PIN Resets
To mitigate risks of account takeovers, SIM-swap attacks, and device cloning:

* **48-Hour Cooling Window**: Post any new UPI registration, change of registered mobile SIM device, or UPI PIN reset/change, a security restriction is applied automatically for 48 hours.
* During this 48-hour cooling period, the maximum total cumulative outward transaction value is restricted to INR 10,000, allowing a maximum of 3 outgoing transactions. Regular transaction limits are reinstated precisely at the 48th hour.

## 3. UPI Lite Small-Value On-Device Wallet
Nova Bank facilitates on-device UPI Lite functionality for swift low-value transactions without PIN entry:

* **Wallet Balance Limit**: The maximum permissible balance in the UPI Lite on-device wallet at any given time is INR 3,500.
* **Single Transaction Limit**: The upper limit for a single offline UPI Lite transaction is INR 800 without requiring UPI PIN authorization.
* **Wallet Top-Up Ceiling**: Wallets can be reloaded from the linked primary business account up to a cumulative maximum of INR 5,000 per calendar day (maximum 2 top-ups of INR 2,500 each).

## 4. Failed Transaction Auto-Reversal and Mandated Compensation TAT
In instances where funds are debited from the sender's account but not credited to the beneficiary merchant or recipient:

* **Harmonized TAT (T+2 Business Days)**: Nova Bank must carry out an automated reversal and credit the funds back into the customer’s business account by the end of the second working day (T+2 days, where T is the transaction date).
* **Delayed Reversal Compensation**: In line with Reserve Bank of India's Harmonisation of TAT directives, if the reversal is delayed beyond T+2 business days, Nova Bank will automatically credit compensation of INR 150 per day of delay directly into the customer's account without necessitating a formal complaint.

## 5. Dispute Resolution, Chargeback Claims, and Timeline
* **Dispute Lodgment Window**: Business account holders can initiate a dispute or chargeback request via the NovaBusiness app or Internet Banking portal within 45 calendar days from the date of the contentious transaction.
* **Resolution Turnaround**: Domestic UPI chargebacks and dual-debit disputes are investigated and resolved conclusively within 10 business days from receipt of the complaint.
* **Provisional Credit**: If a technical reconciliation dispute exceeds 7 business days, Nova Bank extends a temporary provisional credit for the disputed amount pending final network settlement.

## 6. Customer Liability Framework in Unauthorized Digital Banking Transactions
Nova Bank adheres to the RBI Customer Protection framework for determining liability in fraudulent digital transfers:

* **Zero Liability Tier**: The customer incurs zero liability if:
  - Fraud or system failure is attributable to the bank.
  - A third-party security breach occurs where the deficiency is neither with the bank nor the customer, provided the customer notifies Nova Bank within 4 calendar days of receiving the automated SMS/email alert.
* **Limited Liability Tier**: If the unauthorized transaction is reported within 5 to 8 calendar days after the bank alert, customer liability is limited to the transaction value or a maximum of INR 15,000, whichever is less.
* **Full Customer Discretionary Liability**: If the incident is reported after 8 calendar days, the claim is assessed under the bank’s internal board-approved policy.
* **Customer Negligence Exception**: Where the loss results from proven customer compromise—such as sharing UPI MPIN, OTP, or remote screen-sharing access—the customer bears full financial liability until the time the compromise is formally reported to the bank.
