# Outbound Test Guard

Live webhook or WhatsApp delivery test scripts must not run without written
target-number approval.

Required controls:

- Pass `--target-number 90...` on the command line.
- Pass `--confirm-outbound` on the command line.
- Set `CONFIRMED_TARGET_NUMBER=90...` to the exact same number.
- Use a 12 digit Turkish WhatsApp number starting with `90`.

If any control is missing or the numbers do not match, the script exits before
building or sending the live webhook request.

This applies to all test and operation scripts that can trigger outbound
customer, manager, or webhook-driven messages.
