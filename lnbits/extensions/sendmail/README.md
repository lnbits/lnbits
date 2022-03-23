<h1>Sendmail Extension</h1>

This extension allows you to setup a smtp, to offer sending emails with it for a small fee.

## Requirements

- SMTP Server

## Usage

1. Create new emailaddress
2. Verify if email goes to your testemail. Testmail is send on create and update
3. enjoy

## API Endpoints

- **Emailaddresses**
  - GET /api/v1/emailaddress
  - POST /api/v1/emailaddress
  - PUT /api/v1/emailaddress/<domain_id>
  - DELETE /api/v1/emailaddress/<domain_id>
- **Emails**
  - GET /api/v1/email
  - POST /api/v1/email/<emailaddress_id>
  - GET /api/v1/email/<payment_hash>
  - DELETE /api/v1/email/<email_id>
