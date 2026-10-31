import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Measured runs — Computer-use optimisation",
  description:
    "Timed router runs. The 36s, 48s, and 17s figures on the clock are sketches.",
};

const sketches = [
  { time: "36s", what: "Screenshot every step, in a browser" },
  { time: "48s", what: "Cursor on Windows, same sketch" },
  { time: "17s", what: "A Browser Use-style tree agent" },
];

export default function RunsPage() {
  return (
    <>
      <header className="sticky top-0 z-20 border-b border-line bg-ink/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl flex-col items-start gap-2 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <a href="/" className="flex items-center gap-3">
            <span aria-hidden className="size-2.5 shrink-0 bg-amber" />
            <span className="font-mono text-[11px] tracking-[0.18em] uppercase">
              Computer-use optimisation
            </span>
          </a>
          <a
            href="/"
            className="font-mono text-[11px] tracking-[0.16em] text-muted uppercase hover:text-paper"
          >
            Clock
          </a>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-5 py-14 sm:px-8 sm:py-20">
        <p className="font-mono text-[11px] tracking-[0.22em] text-amber uppercase">Measured</p>
        <h1 className="mt-4 max-w-[18ch] font-serif text-6xl leading-[0.9] tracking-[-0.03em] sm:text-7xl">
          Live pages in real Chrome.
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted">
          A pass is a live https page. Wall-clock time includes launching Chrome and any retry. The
          packing list and the local text-box demo stay below, as earlier runs.
        </p>

        <ol className="mt-12 divide-y divide-line border-y border-line">
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">7.77s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Ordinary-language order</h2>
              <p className="mt-2 max-w-xl text-muted">
                Pass. 1 model cycle. The task did not list field names.{" "}
                <a className="underline decoration-line underline-offset-4 hover:text-paper" href="https://httpbin.org/forms/post">
                  https://httpbin.org/forms/post
                </a>{" "}
                echoed Ada Lovelace, 555-0100, ada@example.com, 14:30, medium, bacon, extra cheese,
                onion, mushroom, and the side door at{" "}
                <a className="underline decoration-line underline-offset-4 hover:text-paper" href="https://httpbin.org/post">
                  https://httpbin.org/post
                </a>
                .
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">11.72s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Rejected delivery time</h2>
              <p className="mt-2 max-w-xl text-muted">
                Pass. 2 model cycles. One recovery. 09:00 was rejected, then the same form was sent
                with 11:00. The echo included Grace Hopper, 555-0199, grace@example.com, and the front
                desk.
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">10.55s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Dropdown</h2>
              <p className="mt-2 max-w-xl text-muted">
                Pass. 2 model cycles. One recovery.{" "}
                <a
                  className="underline decoration-line underline-offset-4 hover:text-paper"
                  href="https://www.selenium.dev/selenium/web/web-form.html"
                >
                  https://www.selenium.dev/selenium/web/web-form.html
                </a>{" "}
                submitted Ada Lovelace and the option Two. The confirmation URL contains my-select=2.
                The model named the dropdown and left the option blank. The executor used Two, the one
                option the task named.
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">18.95s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Childhood section</h2>
              <p className="mt-2 max-w-xl text-muted">
                Pass. 4 model cycles. Looked up the Countess of Lovelace, opened Ada Lovelace, and
                opened Childhood.{" "}
                <a
                  className="underline decoration-line underline-offset-4 hover:text-paper"
                  href="https://en.wikipedia.org/wiki/Ada_Lovelace#Childhood"
                >
                  https://en.wikipedia.org/wiki/Ada_Lovelace#Childhood
                </a>
                .
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">7.02s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">httpbin form</h2>
              <p className="mt-2 max-w-xl text-muted">
                Pass. 0 model cycles, under the cap of 2.{" "}
                <a className="underline decoration-line underline-offset-4 hover:text-paper" href="https://httpbin.org/forms/post">
                  https://httpbin.org/forms/post
                </a>{" "}
                echoed Ada Lovelace, 555-0100, ada@example.com, 14:30, and the delivery note at{" "}
                <a className="underline decoration-line underline-offset-4 hover:text-paper" href="https://httpbin.org/post">
                  https://httpbin.org/post
                </a>
                . One batch filled the twelve fields and submitted. No further model call.
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">8.73s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Wikipedia search</h2>
              <p className="mt-2 max-w-xl text-muted">
                Pass. 0 model cycles. The earlier Wikipedia rows were 1 and 2.{" "}
                <a className="underline decoration-line underline-offset-4 hover:text-paper" href="https://en.wikipedia.org/wiki/Main_Page">
                  https://en.wikipedia.org/wiki/Main_Page
                </a>{" "}
                searched for Ada Lovelace. The title was Ada Lovelace - Wikipedia at{" "}
                <a className="underline decoration-line underline-offset-4 hover:text-paper" href="https://en.wikipedia.org/wiki/Ada_Lovelace">
                  https://en.wikipedia.org/wiki/Ada_Lovelace
                </a>
                .
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">8.42s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Python docs heapq</h2>
              <p className="mt-2 max-w-xl text-muted">
                Pass. 0 model cycles. The earlier row was 1.{" "}
                <a className="underline decoration-line underline-offset-4 hover:text-paper" href="https://docs.python.org/3/">
                  https://docs.python.org/3/
                </a>{" "}
                searched for heapq, opened the module, then Priority Queue Implementation Notes. The
                final title was heapq — Heap queue algorithm, at{" "}
                <a
                  className="underline decoration-line underline-offset-4 hover:text-paper"
                  href="https://docs.python.org/3/library/heapq.html#priority-queue-implementation-notes"
                >
                  the section URL
                </a>
                .
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">4.25s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Wikiquote search</h2>
              <p className="mt-2 max-w-xl text-muted">
                Pass. 0 model cycles. The earlier row was 1.{" "}
                <a className="underline decoration-line underline-offset-4 hover:text-paper" href="https://en.wikiquote.org/wiki/Main_Page">
                  https://en.wikiquote.org/wiki/Main_Page
                </a>{" "}
                searched for quincunx. The title was Search results for &quot;quincunx&quot; -
                Wikiquote.
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">5.10s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Wrong click</h2>
              <p className="mt-2 max-w-xl text-muted">
                Pass. 0 model cycles after the miss, under the cap of 2.{" "}
                <a
                  className="underline decoration-line underline-offset-4 hover:text-paper"
                  href="https://docs.python.org/3/search.html?q=heap"
                >
                  https://docs.python.org/3/search.html?q=heap
                </a>{" "}
                clicked Allocating objects on the heap, the title check failed, and the retry opened
                heapq — Heap queue algorithm at{" "}
                <a className="underline decoration-line underline-offset-4 hover:text-paper" href="https://docs.python.org/3/library/heapq.html">
                  https://docs.python.org/3/library/heapq.html
                </a>
                .
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">25.09s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Guardian consent</h2>
              <p className="mt-2 max-w-xl text-muted">
                Pass. 0 model cycles. The form stayed at 0.{" "}
                <a className="underline decoration-line underline-offset-4 hover:text-paper" href="https://www.theguardian.com/uk">
                  https://www.theguardian.com/uk
                </a>{" "}
                kept Accept all inside a frame. The loop dismissed that dialog, then opened Opinion.
                The title was Opinion | The Guardian at{" "}
                <a
                  className="underline decoration-line underline-offset-4 hover:text-paper"
                  href="https://www.theguardian.com/uk/commentisfree"
                >
                  https://www.theguardian.com/uk/commentisfree
                </a>
                . The subscribe choice was not clicked.
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">2.56s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">GitHub login fields</h2>
              <p className="mt-2 max-w-xl text-muted">
                Pass. 0 model cycles. Not submitted.{" "}
                <a className="underline decoration-line underline-offset-4 hover:text-paper" href="https://github.com/login">
                  https://github.com/login
                </a>{" "}
                held not-a-real-user and not-a-real-password. The address stayed on the sign-in page.
              </p>
            </div>
          </li>
        </ol>
        <p className="mt-8 max-w-2xl text-muted">
          BROWSER_USE_API_KEY is unset, so Browser Use did not run. The matched row is the httpbin
          form: pass, 7.02s, 0 model cycles, on https://httpbin.org/forms/post. Fewer model calls
          and a pass is the result recorded here.
        </p>

        <h2 className="mt-20 font-serif text-4xl tracking-[-0.03em]">Earlier router runs.</h2>
        <p className="mt-4 max-w-2xl text-muted">
          These seven were already on the page. Wall-clock time includes launching Chrome.
        </p>
        <ol className="mt-8 divide-y divide-line border-y border-line">
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">4.47s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Packing list</h2>
              <p className="mt-2 max-w-xl text-muted">
                Add milk on the local packing page. Tiers: planner, then fast. The assertion passed.
                The following cycle stopped because the model reply content was null.
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">13.64s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">example.com</h2>
              <p className="mt-2 max-w-xl text-muted">
                Open the page and confirm the heading. Tiers: planner, fast, planner. The fast check
                missed. One retry confirmed the title.
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">3.81s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Biography section</h2>
              <p className="mt-2 max-w-xl text-muted">
                Open the Biography section on the Ada Lovelace article and confirm the title. Tiers:
                planner, direct, planner. The direct check missed. One retry confirmed the title.
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">2.30s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Wikiquote search</h2>
              <p className="mt-2 max-w-xl text-muted">
                Search for quincunx and confirm the title. Tiers: planner, then direct. The search box
                was filled and Search was clicked. No retry.
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">2.55s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Charles Babbage</h2>
              <p className="mt-2 max-w-xl text-muted">
                Follow the Charles Babbage link on the Ada Lovelace article and confirm the title.
                Tiers: planner, then direct. No retry.
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">3.26s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Demo form</h2>
              <p className="mt-2 max-w-xl text-muted">
                Fill a name, an email, and a short message on the local text-box demo, then submit.
                Tiers: planner. One of one cycles used a model. No retry.
              </p>
            </div>
          </li>
          <li className="grid gap-3 py-8 sm:grid-cols-[8rem_minmax(0,1fr)] sm:gap-8">
            <p className="font-serif text-5xl tracking-[-0.03em] text-lime">2.45s</p>
            <div>
              <h2 className="font-serif text-3xl tracking-[-0.02em]">Python docs</h2>
              <p className="mt-2 max-w-xl text-muted">
                Search for heapq, open the module, then open Priority Queue Implementation Notes.
                Tiers: planner, direct, direct. One of three cycles used a model. No retry.
              </p>
            </div>
          </li>
        </ol>
        <p className="mt-8 max-w-2xl text-muted">
          Browser Use still asks a model for every control. These runs were not raced against it.
        </p>

        <section className="mt-16" aria-labelledby="sketches-title">
          <p className="font-mono text-[11px] tracking-[0.22em] text-muted uppercase">Not a measurement</p>
          <h2 id="sketches-title" className="mt-3 font-serif text-4xl tracking-[-0.03em]">
            The older figures are sketches.
          </h2>
          <ul className="mt-8 divide-y divide-line border-y border-line">
            {sketches.map((item) => (
              <li key={item.time} className="grid grid-cols-[5rem_minmax(0,1fr)] items-baseline gap-6 py-5">
                <span className="font-mono text-sm tracking-[0.14em] text-amber">{item.time}</span>
                <span className="text-muted">{item.what}</span>
              </li>
            ))}
          </ul>
        </section>
      </main>
    </>
  );
}
