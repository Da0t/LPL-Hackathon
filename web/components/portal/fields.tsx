"use client";
export type FieldSpec = [string, string, string?, string[]?];
export function Fields({
  fields,
  values,
  onChange,
}: {
  fields: FieldSpec[];
  values: Record<string, any>;
  onChange: (key: string, value: any) => void;
}) {
  return (
    <div className="field-grid">
      {fields.map(([key, label, type = "text", options]) => (
        <label key={key}>
          {label}
          {options ? (
            <select
              value={values[key] ?? ""}
              onChange={(e) => onChange(key, e.target.value)}
            >
              {options.map((o) => (
                <option key={o}>{o}</option>
              ))}
            </select>
          ) : type === "textarea" ? (
            <textarea
              value={values[key] ?? ""}
              onChange={(e) => onChange(key, e.target.value)}
            />
          ) : (
            <input
              type={type}
              value={values[key] ?? ""}
              min={type === "number" ? 0 : undefined}
              step={type === "number" ? "any" : undefined}
              maxLength={key === "ssn_last4" || key === "last4" ? 4 : 500}
              inputMode={
                key === "ssn_last4" || key === "last4" ? "numeric" : undefined
              }
              onChange={(e) =>
                onChange(
                  key,
                  type === "number"
                    ? e.target.value === ""
                      ? ""
                      : Number(e.target.value)
                    : e.target.value,
                )
              }
            />
          )}
        </label>
      ))}
    </div>
  );
}
