import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { Answer } from "@/components/Answer";
import { AskForm } from "@/components/AskForm";
import { SiteHeader } from "@/components/SiteHeader";

export const metadata: Metadata = { title: "Answer · FastBreak" };

async function AskBody({ searchParams }: { searchParams: PageProps<"/ask">["searchParams"] }) {
  const { q } = await searchParams;
  const question = (Array.isArray(q) ? q[0] : q)?.trim() ?? "";
  if (!question) redirect("/");
  return (
    <>
      <AskForm defaultValue={question} />
      <Answer key={question} question={question} />
    </>
  );
}

export default function AskPage({ searchParams }: PageProps<"/ask">) {
  return (
    <>
      <SiteHeader tone="dark" />
      <main className="mx-auto flex w-full max-w-[1120px] flex-col gap-7 px-4 pt-10 pb-16 sm:px-6">
        <Suspense fallback={<AskForm />}>
          <AskBody searchParams={searchParams} />
        </Suspense>
      </main>
    </>
  );
}
