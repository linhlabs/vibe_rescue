// Synthetic browser edge. The offline Atlas inventories this file but cannot
// prove that the Python API receives this request.
export async function sendTicket(message: string, email: string) {
  return fetch("/api/tickets", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ message, email }),
  });
}
