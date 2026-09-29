// §T14 — how the Admin screen words a delivery tally. 0 of 0 is not 100%.
export function deliveryText({ received, undelivered, pending, rate }) {
  if (rate === null) {
    return pending ? `${pending} waiting for a receipt` : 'No notifications sent yet'
  }
  const text = `${received} of ${received + undelivered} delivered (${Math.round(rate * 100)}%)`
  return pending ? `${text}, ${pending} waiting` : text
}
