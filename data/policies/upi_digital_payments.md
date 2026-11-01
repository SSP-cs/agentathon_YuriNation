# Nova Bank UPI & Digital Payments Governance Policy

## 1. UPI Transaction Ceilings and Frequency Thresholds
Nova Bank participates as a Payment Service Provider (PSP) and Issuer Bank on the Unified Payments Interface (UPI) network governed by NPCI and RBI standards.
* **Standard Peer-to-Peer (P2P) Daily Limit**: Retail account holders are restricted to a cumulative transfer limit of INR 1,00,000 per 24-hour rolling window.
* **Transaction Count Limit**: A maximum ceiling of 20 UPI outbound debit transactions is enforced within any consecutive 24-hour window across all UPI third-party app handles linked to the account.
* **High-Value Verified Merchant Category Codes (MCC)**: The daily cap is enhanced to INR 5,00,000 per 24 hours strictly for approved merchant categories:
  - Hospitals and healthcare institutions (MCC 8062, 8011)
  - Educational universities and examination fees (MCC 8220, 8211)
  - Capital market initial public offerings (IPO) and government treasury bonds via UPI ASBA.

## 2. Onboarding Cooling-Off Period for New Devices and PIN Resets
To combat account takeovers, SIM-swap attacks, and device cloning:
* **24-Hour Cooling Window**: Following any new UPI registration, change of registered mobile SIM device, or UPI PIN reset/change, an automatic security restriction applies for exactly 24 hours.
* During this 24-hour cooling period, the maximum total cumulative outward transaction value cannot exceed INR 5,000, and a maximum of 2 outgoing transactions is permitted. Normal transaction limits automatically restore precisely at the 24th hour.

## 3. UPI Lite Small-Value On-Device Wallet
Nova Bank enables on-device UPI Lite functionality for rapid low-value transactions without PIN entry:
* **Wallet Balance Limit**: The maximum permissible balance in the UPI Lite on-device wallet at any given moment is INR 2,000.
* **Single Transaction Limit**: The upper threshold for an individual single offline UPI Lite transaction is INR 500 without requiring UPI PIN authorization.
* **Wallet Top-Up Ceiling**: Wallets may be reloaded from the linked primary savings account up to a cumulative maximum of INR 4,000 per calendar day (maximum 2 top-ups of INR 2,000 each).

## 4. Failed Transaction Auto-Reversal and Mandated Compensation TAT
Where funds are debited from the sender's account but not credited to the beneficiary merchant or recipient:
* **Harmonized TAT (T+1 Business Day)**: Nova Bank must execute an automated reversal and credit the funds back into the customer’s savings account by the end of the next working day (T+1 day, where T is the transaction date).
* **Delayed Reversal Compensation**: Under Reserve Bank of India Harmonisation of TAT directives, if the reversal is delayed beyond T+1 business days, Nova Bank automatically credits compensation of INR 100 per day of delay directly into the customer's account without requiring a formal complaint.

## 5. Dispute Resolution, Chargeback Claims, and Timeline
* **Dispute Lodgment Window**: Account holders can raise a dispute or chargeback request through the NovaMobile application or Internet Banking portal within 30 calendar days from the date of the contentious transaction.
* **Resolution Turnaround**: Domestic UPI chargebacks and dual-debit disputes are investigated and definitively resolved within 7 business days from receipt of the complaint.
* **Provisional Credit**: If a technical reconciliation dispute exceeds 5 business days, Nova Bank issues a temporary provisional credit for the disputed amount pending final beneficiary network settlement.

## 6. Customer Liability Framework in Unauthorized Digital Banking Transactions
Nova Bank strictly adheres to the RBI Customer Protection framework determining liability in fraudulent digital transfers:
* **Zero Liability Tier**: The customer incurs zero financial liability if:
  - Fraud or system failure occurs on the part of the bank.
  - A third-party security breach occurs where the deficiency lies neither with the bank nor the customer, provided the customer notifies Nova Bank within 3 calendar days of receiving the automated SMS/email alert.
* **Limited Liability Tier**: If the unauthorized transaction is reported within 4 to 7 calendar days after the bank alert, customer liability is limited to the transaction value or a maximum of INR 10,000, whichever is lower.
* **Full Customer Discretionary Liability**: If the incident is reported after 7 calendar days, the claim is evaluated under the bank’s internal board-approved policy.
* **Customer Negligence Exception**: Where the loss is due to proven customer compromise—such as sharing UPI MPIN, OTP, or remote screen-sharing access—the customer bears full financial liability until the time the compromise is formally reported to the bank.

