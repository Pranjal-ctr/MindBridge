/**
 * ChatMessage — renders a single conversation bubble.
 *
 * - Comrade (AI) replies are rendered as Markdown so lists, bold, headings and
 *   links from the model come through formatted instead of as raw asterisks.
 * - User messages stay plain text (no Markdown) so nothing they type is
 *   interpreted as markup.
 * - The single freshest AI reply reveals with a typewriter effect (plain while
 *   typing, then the final Markdown), and every bubble fades/slides in.
 */

import { useEffect, useRef, useState } from 'react';
import { Brain } from 'lucide-react';
import { motion } from 'motion/react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';
import type { MessageResponse } from '../../lib/types';

// Tailwind styling for the Markdown elements Comrade tends to emit.
const markdownComponents: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
  ul: ({ children }) => <ul className="list-disc pl-5 mb-2 last:mb-0 space-y-1">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-5 mb-2 last:mb-0 space-y-1">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  h1: ({ children }) => <h1 className="text-base font-semibold mb-2 mt-1">{children}</h1>,
  h2: ({ children }) => <h2 className="text-base font-semibold mb-2 mt-1">{children}</h2>,
  h3: ({ children }) => <h3 className="text-sm font-semibold mb-2 mt-1">{children}</h3>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-secondary underline underline-offset-2">
      {children}
    </a>
  ),
  code: ({ children }) => (
    <code className="px-1 py-0.5 rounded bg-black/10 text-[0.85em] font-mono">{children}</code>
  ),
  pre: ({ children }) => (
    <pre className="bg-black/10 rounded-lg p-3 overflow-x-auto text-sm mb-2 last:mb-0">{children}</pre>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-current/30 pl-3 italic opacity-90 mb-2 last:mb-0">{children}</blockquote>
  ),
};

interface ChatMessageProps {
  message: MessageResponse;
  /** When true, this AI reply animates in with a typewriter effect (used for the freshest reply only). */
  typewriter?: boolean;
  /** Called as revealed text grows so the parent can keep the view scrolled to the bottom. */
  onGrow?: () => void;
}

export function ChatMessage({ message, typewriter = false, onGrow }: ChatMessageProps) {
  const isUser = message.sender_type === 'user';
  const fullText = message.message_text;

  const [revealed, setRevealed] = useState(typewriter ? '' : fullText);
  const [done, setDone] = useState(!typewriter);
  const onGrowRef = useRef(onGrow);
  onGrowRef.current = onGrow;

  useEffect(() => {
    if (!typewriter) {
      setRevealed(fullText);
      setDone(true);
      return;
    }

    setRevealed('');
    setDone(false);
    let i = 0;
    // Reveal ~150 ticks regardless of length so long replies don't crawl.
    const step = Math.max(2, Math.ceil(fullText.length / 150));
    const id = window.setInterval(() => {
      i += step;
      if (i >= fullText.length) {
        setRevealed(fullText);
        setDone(true);
        window.clearInterval(id);
      } else {
        setRevealed(fullText.slice(0, i));
      }
      onGrowRef.current?.();
    }, 18);

    return () => window.clearInterval(id);
  }, [typewriter, fullText]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#5A6BFF] to-[#232B6D] flex items-center justify-center flex-shrink-0 mt-1 mr-2">
          <Brain className="w-4 h-4 text-white" />
        </div>
      )}
      <div
        className={`max-w-[80%] md:max-w-[70%] rounded-2xl px-4 py-3 text-[0.95rem] ${
          isUser ? 'bg-primary text-primary-foreground whitespace-pre-wrap' : 'bg-muted text-foreground'
        }`}
      >
        {isUser || !done ? (
          <span className="whitespace-pre-wrap">
            {revealed}
            {!done && <span className="inline-block w-1.5 h-4 -mb-0.5 ml-0.5 bg-current/60 animate-pulse" />}
          </span>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {fullText}
          </ReactMarkdown>
        )}
      </div>
    </motion.div>
  );
}
