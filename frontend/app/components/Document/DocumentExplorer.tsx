"use client";
import React, { useState, useEffect } from "react";
import { FaInfoCircle } from "react-icons/fa";
import VectorView from "./VectorView";
import ChunkView from "./ChunkView";
import InfoComponent from "../Navigation/InfoComponent";

import DocumentMetaView from "./DocumentMetaView";

import { MdCancel } from "react-icons/md";
import { MdContentPaste } from "react-icons/md";
import { MdContentCopy } from "react-icons/md";
import { TbVectorTriangle } from "react-icons/tb";
import ContentView from "./ContentView";
import { IoMdAddCircle } from "react-icons/io";
import { FaExternalLinkAlt } from "react-icons/fa";
import {
  NemiDocument,
  DocumentPayload,
  Credentials,
  ChunkScore,
  Theme,
  DocumentFilter,
} from "@/app/types";

import NemiButton from "../Navigation/NemiButton";

import { fetchSelectedDocument } from "@/app/api";

interface DocumentExplorerProps {
  selectedDocument: string | null;
  setSelectedDocument: (c: string | null) => void;
  chunkScores?: ChunkScore[];
  credentials: Credentials;
  selectedTheme: Theme;
  production: "Local" | "Demo" | "Production";
  documentFilter: DocumentFilter[];
  setDocumentFilter: React.Dispatch<React.SetStateAction<DocumentFilter[]>>;
  addStatusMessage: (
    message: string,
    type: "INFO" | "WARNING" | "SUCCESS" | "ERROR"
  ) => void;
}

const DocumentExplorer: React.FC<DocumentExplorerProps> = ({
  credentials,
  selectedDocument,
  setSelectedDocument,
  chunkScores,
  production,
  selectedTheme,
  documentFilter,
  setDocumentFilter,
  addStatusMessage,
}) => {
  const [selectedSetting, setSelectedSetting] = useState<
    "Content" | "Chunks" | "Metadata" | "Config" | "Vector Space" | "Graph"
  >("Content");

  const [isFetching, setIsFetching] = useState(false);
  const [document, setDocument] = useState<NemiDocument | null>(null);

  useEffect(() => {
    if (selectedDocument) {
      handleFetchSelectedDocument();
    } else {
      setDocument(null);
    }
  }, [selectedDocument]);

  const handleSourceClick = (url: string) => {
    // Open a new tab with the specified URL
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const handleFetchSelectedDocument = async () => {
    try {
      setIsFetching(true);

      const data: DocumentPayload | null = await fetchSelectedDocument(
        selectedDocument,
        credentials
      );

      if (data) {
        if (data.error !== "") {
          console.error(data.error);
          setIsFetching(false);
          setDocument(null);
          setSelectedDocument(null);
        } else {
          setDocument(data.document);
          setIsFetching(false);
        }
      }
    } catch (error) {
      console.error("Failed to fetch document:", error);
      setIsFetching(false);
    }
  };

  if (!selectedDocument) {
    return <div></div>;
  }

  return (
    <div className="flex flex-col gap-2 w-full">
      {/* Search Header */}
      <div className="bg-bg-alt-nemi rounded-2xl flex gap-2 p-3 items-center justify-end lg:justify-between h-min w-full">
        <div className="hidden lg:flex gap-2 justify-start ">
          <InfoComponent
            tooltip_text="Inspect your all information about your document, such as chunks, metadata and more."
            display_text={document ? document.title : "Loading..."}
          />
        </div>
        <div className="flex gap-3 justify-end">
          <NemiButton
            title="Content"
            Icon={MdContentPaste}
            onClick={() => setSelectedSetting("Content")}
            selected={selectedSetting === "Content"}
            selected_color="bg-secondary-nemi"
          />

          <NemiButton
            title="Chunks"
            Icon={MdContentCopy}
            onClick={() => setSelectedSetting("Chunks")}
            selected={selectedSetting === "Chunks"}
            selected_color="bg-secondary-nemi"
          />

          <NemiButton
            title="Vector"
            Icon={TbVectorTriangle}
            onClick={() => setSelectedSetting("Vector Space")}
            selected={selectedSetting === "Vector Space"}
            selected_color="bg-secondary-nemi"
          />

          <NemiButton
            Icon={MdCancel}
            onClick={() => {
              setSelectedDocument(null);
            }}
          />
        </div>
      </div>

      {/* Document List */}
      <div className="bg-bg-alt-nemi rounded-2xl flex flex-col p-6 h-full w-full overflow-y-auto overflow-x-hidden">
        {selectedSetting === "Content" && (
          <ContentView
            selectedTheme={selectedTheme}
            document={document}
            credentials={credentials}
            selectedDocument={selectedDocument}
            chunkScores={chunkScores}
          />
        )}

        {selectedSetting === "Chunks" && (
          <ChunkView
            selectedTheme={selectedTheme}
            credentials={credentials}
            selectedDocument={selectedDocument}
          />
        )}

        {selectedSetting === "Vector Space" && (
          <VectorView
            credentials={credentials}
            selectedDocument={selectedDocument}
            chunkScores={chunkScores}
            production={production}
          />
        )}

        {selectedSetting === "Metadata" && (
          <DocumentMetaView
            credentials={credentials}
            selectedDocument={selectedDocument}
          />
        )}
      </div>

      {/* Import Footer */}
      <div className="bg-bg-alt-nemi rounded-2xl flex gap-2 p-3 items-center justify-between h-min w-full">
        <div className="flex gap-3">
          {documentFilter.some(
            (filter) => filter.uuid === selectedDocument
          ) && (
            <NemiButton
              title="Delete from Chat"
              Icon={MdCancel}
              selected={true}
              selected_color="bg-warning-nemi"
              onClick={() => {
                setDocumentFilter(
                  documentFilter.filter((f) => f.uuid !== selectedDocument)
                );
                addStatusMessage("Removed document from Chat", "INFO");
              }}
            />
          )}
          {!documentFilter.some((filter) => filter.uuid === selectedDocument) &&
            document && (
              <NemiButton
                title="Add to Chat"
                Icon={IoMdAddCircle}
                onClick={() => {
                  setDocumentFilter([
                    ...documentFilter,
                    { uuid: selectedDocument, title: document.title },
                  ]);
                  addStatusMessage("Added document to Chat", "SUCCESS");
                }}
              />
            )}
        </div>
        <div className="flex gap-3">
          {selectedDocument && document && document.source && (
            <NemiButton
              title="Go To Source"
              Icon={FaExternalLinkAlt}
              onClick={() => {
                handleSourceClick(document.source);
              }}
            />
          )}
          <NemiButton
            title="Document Info"
            Icon={FaInfoCircle}
            onClick={() => setSelectedSetting("Metadata")}
            selected={selectedSetting === "Metadata"}
            selected_color="bg-secondary-nemi"
          />
        </div>
      </div>
    </div>
  );
};

export default DocumentExplorer;
