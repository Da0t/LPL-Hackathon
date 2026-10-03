import React from "react";
import { Reveal } from "./reveal";
import { AwsServiceIcon, ClaudeMark } from "@/components/brand-logos";

const SERVICES = [
  {
    kind: "bedrock" as const,
    name: "Amazon Bedrock",
    body: "Interprets the request, asks one question at a time, and classifies the confirmed case. Claude Haiku 4.5 through the Converse API, with narrow tools that read only the client’s own accounts and an approved glossary.",
    extra: true,
  },
  {
    kind: "transcribe" as const,
    name: "Amazon Transcribe",
    body: "Live speech to text with a custom vocabulary of financial terms, so “R O I” and “1099-R” arrive as the words they mean.",
  },
  {
    kind: "cognito" as const,
    name: "Amazon Cognito",
    body: "Sign-in for clients and staff. The demo sign-ins are generated at provisioning and never emailed.",
  },
  {
    kind: "dynamodb" as const,
    name: "Amazon DynamoDB",
    body: "Client profiles, accounts, and history in a private table. Synthetic data only.",
  },
];

export default function AwsStack() {
  return (
    <section className="relative z-10 border-t border-border bg-background py-24 lg:py-32">
      <div className="mx-auto max-w-6xl px-6">
        <Reveal className="max-w-2xl">
          <h2 className="text-balance text-3xl font-semibold tracking-tight md:text-5xl">What runs on AWS, and why.</h2>
          <p className="mt-4 text-pretty text-lg text-muted-foreground">
            Four services, each with one job. Everything runs in us-east-1 with least-privilege roles and no keys in code.
          </p>
        </Reveal>
        <Reveal className="mt-14 grid gap-x-12 gap-y-10 md:grid-cols-2" delay={0.1}>
          {SERVICES.map((s) => (
            <div key={s.kind} className="flex gap-5">
              <AwsServiceIcon kind={s.kind} size={48} className="shrink-0" />
              <div>
                <h3 className="flex items-center gap-2 text-lg font-semibold tracking-tight">
                  {s.name}
                  {s.extra && (
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-border px-2 py-[2px] text-[11.5px] font-normal text-muted-foreground">
                      <ClaudeMark height={12} /> Claude Haiku 4.5
                    </span>
                  )}
                </h3>
                <p className="mt-2 text-pretty text-[15px] leading-relaxed text-muted-foreground">{s.body}</p>
              </div>
            </div>
          ))}
        </Reveal>
      </div>
    </section>
  );
}
