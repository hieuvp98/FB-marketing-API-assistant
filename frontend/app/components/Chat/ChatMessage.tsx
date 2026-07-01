"use client";

import React from "react";
import { ChunkScore, Message } from "@/app/types";
import ReactMarkdown from "react-markdown";
import { FaDatabase } from "react-icons/fa";
import { BiError } from "react-icons/bi";
import { IoNewspaper } from "react-icons/io5";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { IoDocumentAttach } from "react-icons/io5";
import {
  oneDark,
  oneLight,
} from "react-syntax-highlighter/dist/cjs/styles/prism";

import NemiButton from "../Navigation/NemiButton";

import { Theme } from "@/app/types";

interface ChatMessageProps {
  message: Message;
  message_index: number;
  selectedTheme: Theme;
  selectedDocument: string | null;
  setSelectedDocument: (s: string | null) => void;
  setSelectedDocumentScore: (s: string | null) => void;
  setSelectedChunkScore: (s: ChunkScore[]) => void;
}

const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  selectedTheme,
  selectedDocument,
  setSelectedDocument,
  message_index,
  setSelectedDocumentScore,
  setSelectedChunkScore,
}) => {
  const colorTable = {
    user: "bg-bg-nemi",
    system: "bg-bg-alt-nemi",
    error: "bg-warning-nemi",
    retrieval: "bg-bg-nemi",
  };

  if (typeof message.content === "string") {
    return (
      <div
        className={`flex items-end gap-2 ${message.type === "user" ? "justify-end" : "justify-start"}`}
      >
        <div
          className={`flex flex-col items-start p-5 rounded-3xl animate-press-in text-sm lg:text-base ${colorTable[message.type]}`}
        >
          {message.cached && (
            <FaDatabase size={12} className="text-text-nemi" />
          )}
          {message.type === "system" && (
            <ReactMarkdown
              className="prose md:prose-sm lg:prose-base p-3 prose-pre:bg-bg-alt-nemi"
              components={{
                code({ node, inline, className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || "");
                  return !inline && match ? (
                    <SyntaxHighlighter
                      style={
                        selectedTheme.theme === "dark"
                          ? (oneDark as any)
                          : (oneLight as any)
                      }
                      language={match[1]}
                      PreTag="div"
                      {...props}
                    >
                      {String(children).replace(/\n$/, "")}
                    </SyntaxHighlighter>
                  ) : (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          )}
          {message.type === "user" && (
            <div className="whitespace-pre-wrap">{message.content}</div>
          )}
          {message.type === "error" && (
            <div className="whitespace-pre-wrap flex items-center gap-2 text-sm text-text-nemi">
              <BiError size={15} />
              <p>{message.content}</p>
            </div>
          )}
        </div>
      </div>
    );
  } else {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 w-full items-center">
        {message.content.map((document, index) => (
          <button
            onClick={() => {
              setSelectedDocument(document.uuid);
              setSelectedDocumentScore(
                document.uuid + document.score + document.chunks.length
              );
              setSelectedChunkScore(document.chunks);
            }}
            key={"Retrieval" + document.title + index}
            className={`flex ${selectedDocument && selectedDocument === document.uuid + document.score + document.chunks.length ? "bg-secondary-nemi hover:bg-button-hover-nemi" : "bg-button-nemi hover:bg-secondary-nemi"} rounded-3xl p-3 items-center justify-between transition-colors duration-300 ease-in-out border-none`}
          >
            <div className="flex items-center justify-between w-full">
              <p
                className="text-xs flex-grow truncate mr-2"
                title={document.title}
              >
                {document.title}
              </p>
              <div className="flex gap-1 items-center text-text-nemi flex-shrink-0">
                <IoNewspaper size={12} />
                <p className="text-sm">{document.chunks.length}</p>
              </div>
            </div>
          </button>
        ))}
        <NemiButton
          Icon={IoDocumentAttach}
          className="btn-sm btn-square"
          onClick={() =>
            (
              document.getElementById(
                "context-modal-" + message_index
              ) as HTMLDialogElement
            ).showModal()
          }
        />
        <dialog id={"context-modal-" + message_index} className="modal">
          <div className="modal-box">
            <h3 className="font-bold text-lg">Context</h3>
            <p className="py-4">{message.context}</p>
            <div className="modal-action">
              <form method="dialog">
                <button className="btn focus:outline-none text-text-alt-nemi bg-button-nemi hover:bg-button-hover-nemi hover:text-text-nemi border-none shadow-none">
                  <p>Close</p>
                </button>
              </form>
            </div>
          </div>
        </dialog>
      </div>
    );
  }
};

export default ChatMessage;
