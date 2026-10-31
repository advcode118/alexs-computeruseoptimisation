# Who pays for speed

QA, data entry, and scraping teams pay. A model call is billed to the Nebius key of the person running the loop, and waiting is their time. QA pays it on form checks and sign-in pages. Data entry pays it on orders, addresses, and lists. Scraping pays it on search and on opening a saved page. The direct role-and-name path spends neither a call nor a wait on a task it can finish from the accessibility tree.

The bench dollars are an estimate from the rate table and the API token counts. They are not an invoice.

On the pinned baseline, one action per model call, the median task took 8.435 s and about 0.00268524 estimated dollars. With the direct path left on, the median task took 0.332 s and 0.0 estimated dollars. Success stayed at 1.0 on the main tasks and on the holdout.

## Ten tasks shaped like the work

Each one is a local fixture or a saved replay. A code check on the DOM, the URL, or the field values decides pass or fail.

1. `pack-milk` — add one item to a packing list.
2. `invoice-ada` — fill an order form and submit it.
3. `login-hold` — fill a sign-in form and leave it unsubmitted.
4. `profile-hold` — fill a profile and leave it unsubmitted.
5. `catalog-wool` — search a catalog.
6. `open-childhood` — open a section from a saved contents page.
7. `docs-heapq` — search documentation and open the matching page.
8. `newsletter-optin` — fill an email, choose the newsletter, and submit.
9. `delivery-radio` — fill a reference and choose a delivery option.
10. `address-office` — fill a four-field address and submit it.
