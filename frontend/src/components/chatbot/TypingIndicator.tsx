'use client';

interface TypingIndicatorProps {
  status?: string;
}

export function TypingIndicator({ status }: TypingIndicatorProps) {
  return (
    <div className="flex items-center gap-1 px-4 py-2">
      <div className="flex gap-1">
        <span
          className="h-2 w-2 rounded-full bg-[#3b82f6] animate-bounce"
          style={{ animationDelay: '0ms' }}
        />
        <span
          className="h-2 w-2 rounded-full bg-[#3b82f6] animate-bounce"
          style={{ animationDelay: '150ms' }}
        />
        <span
          className="h-2 w-2 rounded-full bg-[#3b82f6] animate-bounce"
          style={{ animationDelay: '300ms' }}
        />
      </div>
      <span className="ml-2 text-sm text-slate-500">
        {status || 'Processing...'}
      </span>
    </div>
  );
}
