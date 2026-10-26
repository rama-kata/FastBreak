import Form from "next/form";

const MAX_CHARS = 300; // the API's limit

export function AskForm({ defaultValue = "", large = false }: { defaultValue?: string; large?: boolean }) {
  return (
    <Form action="/ask" className="flex w-full flex-wrap gap-2.5">
      <label htmlFor="q" className="sr-only">
        Your question
      </label>
      <input
        id="q"
        name="q"
        type="text"
        required
        maxLength={MAX_CHARS}
        defaultValue={defaultValue}
        placeholder="Who has the most 20-point games off the bench since 2015?"
        className={`min-w-0 flex-[999_1_420px] rounded-xl border-[1.5px] border-line-strong bg-white px-5 text-[17px] text-ink placeholder:text-muted focus:border-navy focus:outline-none ${large ? "h-[60px]" : "h-14"}`}
      />
      <button
        type="submit"
        className={`flex-[1_0_auto] cursor-pointer rounded-xl bg-sun px-7 font-display text-lg font-bold text-ink hover:brightness-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-navy ${large ? "h-[60px]" : "h-14"}`}
      >
        Ask
      </button>
    </Form>
  );
}
