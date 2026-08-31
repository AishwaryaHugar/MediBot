import { Source } from "../lib/api";

const COLLECTION_COLORS: Record<string, string> = {
  clinical:  "bg-blue-100   text-blue-800",
  nursing:   "bg-green-100  text-green-800",
  billing:   "bg-yellow-100 text-yellow-800",
  equipment: "bg-orange-100 text-orange-800",
  general:   "bg-gray-100   text-gray-700",
};

interface Props {
  sources: Source[];
}

export default function SourceCitation({ sources }: Props) {
  if (!sources.length) return null;

  return (
    <div className="mt-3 space-y-2">
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Sources</p>
      {sources.map((s, i) => (
        <div key={i} className="flex items-start gap-2 bg-gray-50 rounded-lg px-3 py-2 text-xs">
          <span className={`shrink-0 px-2 py-0.5 rounded-full font-medium text-[11px] ${COLLECTION_COLORS[s.collection] ?? "bg-gray-100 text-gray-600"}`}>
            {s.collection}
          </span>
          <div className="min-w-0">
            <p className="font-medium text-gray-700 truncate">{s.section_title}</p>
            <p className="text-gray-400 truncate">{s.source_document}</p>
          </div>
          {s.score !== undefined && (
            <span className="ml-auto shrink-0 text-gray-400">
              {s.score.toFixed(3)}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
