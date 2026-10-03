"use client";
import { useState } from "react";
import { Save, CheckCircle2, ShieldCheck } from "lucide-react";
import { useClient, PageHeading } from "@/components/portal/shell";
import { Fields, FieldSpec } from "@/components/portal/fields";
import { portalApi, Client } from "@/lib/portal";
const groups: { name: string; description: string; fields: FieldSpec[] }[] = [
  {
    name: "Personal information",
    description: "The details that make this workspace yours.",
    fields: [
      ["legal_name", "Legal name"],
      ["preferred_name", "Preferred name"],
      ["date_of_birth", "Date of birth", "date"],
      ["ssn_last4", "Social Security number · last 4 only"],
      [
        "marital_status",
        "Marital status",
        "text",
        ["Single", "Married", "Divorced", "Widowed", "Domestic partnership"],
      ],
      ["citizenship", "Citizenship"],
      ["tax_residency", "Tax residency"],
      [
        "tax_filing_status",
        "Tax filing status",
        "text",
        [
          "Single",
          "Married filing jointly",
          "Married filing separately",
          "Head of household",
        ],
      ],
    ],
  },
  {
    name: "Contact & address",
    description: "Where and how you prefer to hear from your team.",
    fields: [
      ["email", "Contact email", "email"],
      ["phone", "Phone", "tel"],
      ["street", "Street address"],
      ["address_line2", "Apartment / suite"],
      ["city", "City"],
      ["state", "State code"],
      ["postal_code", "ZIP / postal code"],
      ["country", "Country"],
      ["preferred_contact", "Preferred contact", "text", ["email", "phone"]],
      [
        "meeting_preference",
        "Meeting preference",
        "text",
        ["video", "phone", "in_person"],
      ],
    ],
  },
  {
    name: "Employment & household",
    description: "Useful context for your financial conversations.",
    fields: [
      [
        "employment_status",
        "Employment status",
        "text",
        ["Employed", "Self-employed", "Retired", "Not employed", "Student"],
      ],
      ["employer", "Employer / business"],
      ["occupation", "Occupation"],
      ["annual_income", "Annual household income (USD)", "number"],
      ["monthly_expenses", "Monthly expenses (USD)", "number"],
      ["liabilities", "Total liabilities (USD)", "number"],
      ["net_worth", "Estimated net worth (USD)", "number"],
      ["liquid_net_worth", "Estimated liquid net worth (USD)", "number"],
    ],
  },
  {
    name: "Goals & preferences",
    description: "Your own preferences, for your advisor to discuss with you.",
    fields: [
      [
        "investment_objective",
        "Primary objective",
        "text",
        [
          "Retirement income",
          "Long-term growth",
          "Legacy planning",
          "Capital preservation",
          "Education savings",
        ],
      ],
      [
        "risk_tolerance",
        "Risk preference",
        "text",
        ["Conservative", "Moderate", "Growth-oriented"],
      ],
      [
        "time_horizon",
        "Time horizon",
        "text",
        ["Under 3 years", "3–5 years", "5–10 years", "10+ years"],
      ],
      [
        "investment_experience",
        "Investment experience",
        "text",
        ["New to investing", "Intermediate", "Experienced"],
      ],
      ["retirement_age", "Planned retirement age", "number"],
      ["emergency_fund_months", "Emergency savings goal (months)", "number"],
      ["liquidity_needs", "Upcoming cash needs"],
      ["notes", "Additional context", "textarea"],
    ],
  },
  {
    name: "Trusted contact",
    description:
      "A contact record only. This does not grant account access or authority.",
    fields: [
      ["trusted_contact", "Full name"],
      ["trusted_contact_relationship", "Relationship"],
      ["trusted_contact_phone", "Phone", "tel"],
    ],
  },
];
export default function Profile() {
  const { client, setClient } = useClient();
  const [form, setForm] = useState({ ...client.profile }),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(""),
    [error, setError] = useState("");
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setNotice("");
        setError("");
        try {
          const updated = await portalApi<Client>("/portal/profile", "PUT", {
            revision: client.revision,
            profile: form,
          });
          setClient(updated);
          setNotice("Your profile was saved.");
        } catch (e: any) {
          setError(e.message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <PageHeading
        eyebrow="MY PROFILE"
        title="A little more about you."
        description="Keep your details current so every conversation starts with the right context."
        action={
          <button className="portal-primary" disabled={busy}>
            <Save size={17} />
            {busy ? "Saving…" : "Save profile"}
          </button>
        }
      />
      <div className="profile-note">
        <ShieldCheck size={18} /> Only the last four SSN digits are stored. Use
        fictional information in this prototype. Contact email changes do not
        change your sign-in email.
      </div>
      {error && (
        <p className="portal-error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="portal-success" role="status">
          <CheckCircle2 size={18} />
          {notice}
        </p>
      )}
      {groups.map((g) => (
        <section key={g.name} className="portal-card profile-section">
          <div>
            <h2>{g.name}</h2>
            <p>{g.description}</p>
          </div>
          <Fields
            fields={g.fields}
            values={form}
            onChange={(k, v) => {
              setForm((f) => ({ ...f, [k]: v }));
              setNotice("");
            }}
          />
        </section>
      ))}
      <div className="form-footer">
        <span>Your changes are saved only when you choose Save.</span>
        <button className="portal-primary" disabled={busy}>
          {busy ? "Saving…" : "Save profile"}
        </button>
      </div>
    </form>
  );
}
