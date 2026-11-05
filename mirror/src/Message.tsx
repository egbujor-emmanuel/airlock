import { Fragment } from "react";

const REDACTED = /\[REDACTED:([a-z_]+)#(\d+)\]/g;
const QUERY = /❓ Query (Q-[A-Z]+-\d+): ([\s\S]*?)\n```json\n([\s\S]*?)\n```/;
const ANSWER_LINE = /^• ([a-z0-9_]+) = (.+)$/;

/** Text with each redaction drawn as a solid bar naming what was withheld. */
function Redacted({ text }: { text: string }) {
  const parts: React.ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(REDACTED)) {
    parts.push(text.slice(last, match.index));
    parts.push(
      <span key={match.index} className="redact" title={`withheld: ${match[1]}`}>
        {match[1].replaceAll("_", " ")}
      </span>,
    );
    last = (match.index ?? 0) + match[0].length;
  }
  parts.push(text.slice(last));
  return <>{parts}</>;
}

/** A field type as words and chips: `enum:a|b[]` reads "list of: a b". */
function TypeChips({ spec }: { spec: string }) {
  const isList = spec.endsWith("[]");
  const core = isList ? spec.slice(0, -2) : spec;
  const options = core.startsWith("enum:") ? core.slice(5).split("|") : null;
  return (
    <span className="type">
      {isList && <span className="type-word">list of</span>}
      {options ? (
        options.map((o) => (
          <span key={o} className="chip-opt">
            {o}
          </span>
        ))
      ) : (
        <span className="type-word">{core}</span>
      )}
    </span>
  );
}

/** An answered value: arrays become chips. */
function ValueChips({ value }: { value: string }) {
  try {
    const parsed: unknown = JSON.parse(value);
    if (Array.isArray(parsed)) {
      return (
        <span className="type">
          {parsed.map((v) => (
            <span key={String(v)} className="chip-opt val">
              {String(v)}
            </span>
          ))}
        </span>
      );
    }
    return <span className="val-scalar">{String(parsed)}</span>;
  } catch {
    return <span className="val-scalar">{value}</span>;
  }
}

function Query({ id, question, fields }: { id: string; question: string; fields: Record<string, string> }) {
  return (
    <div className="typed">
      <div className="typed-head">
        <span className="tag">typed query</span> <span className="mono">{id}</span>
      </div>
      <p>{question}</p>
      <dl>
        {Object.entries(fields).map(([name, type]) => (
          <Fragment key={name}>
            <dt className="mono">{name}</dt>
            <dd>
              <TypeChips spec={type} />
            </dd>
          </Fragment>
        ))}
      </dl>
    </div>
  );
}

function Answer({ id, values }: { id: string; values: [string, string][] }) {
  return (
    <div className="typed">
      <div className="typed-head">
        <span className="tag">typed answer</span> <span className="mono">{id}</span>
        <span className="dim"> · values only, no free text</span>
      </div>
      <dl>
        {values.map(([name, value]) => (
          <Fragment key={name}>
            <dt className="mono">{name}</dt>
            <dd>
              <ValueChips value={value} />
            </dd>
          </Fragment>
        ))}
      </dl>
    </div>
  );
}

export function Message({ text }: { text: string }) {
  const query = text.match(QUERY);
  if (query) {
    const fields = (JSON.parse(query[3]) as { fields: Record<string, string> }).fields;
    return <Query id={query[1]} question={query[2].trim()} fields={fields} />;
  }
  if (text.startsWith("📊 Answer to query")) {
    const id = text.match(/Q-[A-Z]+-\d+/)?.[0] ?? "";
    const values = text
      .split("\n")
      .map((line) => line.match(ANSWER_LINE))
      .filter((m): m is RegExpMatchArray => m !== null)
      .map((m) => [m[1], m[2]] as [string, string]);
    return <Answer id={id} values={values} />;
  }
  return (
    <p className="body">
      <Redacted text={text} />
    </p>
  );
}
