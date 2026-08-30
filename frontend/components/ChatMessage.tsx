import { ChatResponse } from "../lib/api";
import SourceCitation from "./SourceCitation";

interface Message {
  role: "user" | "assistant";
  content: string;
  response?: ChatResponse;
}

interface Props {
  message: Message;
}

function renderInline(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

function MarkdownContent({ text }: { text: string }) {
  const lines = text.split("\n");
  const nodes: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Table block
    if (line.trimStart().startsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trimStart().startsWith("|")) {
        tableLines.push(lines[i]);
        i++;
      }
      const rows = tableLines.filter((l) => !/^\|[-| :]+\|$/.test(l.trim()));
      const parseCells = (l: string) =>
        l.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());

      nodes.push(
        <div key={nodes.length} className="overflow-x-auto my-2">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr>
                {parseCells(rows[0]).map((cell, ci) => (
                  <th key={ci} className="border border-gray-300 bg-gray-100 px-3 py-1.5 text-left font-semibold">
                    {renderInline(cell)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.slice(1).map((row, ri) => (
                <tr key={ri} className={ri % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                  {parseCells(row).map((cell, ci) => (
                    <td key={ci} className="border border-gray-300 px-3 py-1.5">
                      {renderInline(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    // Heading
    if (line.startsWith("### ")) {
      nodes.push(<h3 key={nodes.length} className="font-semibold text-sm mt-2">{renderInline(line.slice(4))}</h3>);
    } else if (line.startsWith("## ")) {
      nodes.push(<h2 key={nodes.length} className="font-semibold text-sm mt-2">{renderInline(line.slice(3))}</h2>);
    // List item
    } else if (/^[-*] /.test(line)) {
      nodes.push(<li key={nodes.length} className="ml-4 list-disc">{renderInline(line.slice(2))}</li>);
    // Blank line
    } else if (line.trim() === "") {
      nodes.push(<br key={nodes.length} />);
    // Normal paragraph
    } else {
      nodes.push(<p key={nodes.length}>{renderInline(line)}</p>);
    }

    i++;
  }

  return <div className="space-y-0.5">{nodes}</div>;
}

export default function ChatMessage({ message }: Props) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-[75%] bg-brand-600 text-white rounded-2xl rounded-br-sm px-4 py-3 text-sm shadow-sm">
          {message.content}
        </div>
      </div>
    );
  }

  const res = message.response;
  const isSQL = res?.retrieval_type === "sql_rag";

  return (
    <div className="flex justify-start mb-4">
      <div className="max-w-[82%]">
        <div className="flex items-center gap-2 mb-1.5">
          <div className="w-6 h-6 bg-brand-600 rounded-full flex items-center justify-center text-white text-xs font-bold">M</div>
          <span className="text-xs text-gray-400">MediBot</span>
          {res && (
            <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${isSQL ? "bg-purple-100 text-purple-700" : "bg-teal-100 text-teal-700"}`}>
              {isSQL ? "SQL Analytics" : "Knowledge Base"}
            </span>
          )}
        </div>
        <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-gray-800 shadow-sm">
          <MarkdownContent text={message.content} />
          {res?.sources && <SourceCitation sources={res.sources} />}
        </div>
      </div>
    </div>
  );
}

export type { Message };
