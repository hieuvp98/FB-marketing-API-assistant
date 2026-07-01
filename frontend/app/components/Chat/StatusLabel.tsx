"use client";

import React from "react";

interface StatusLabelProps {
  status: boolean;
  true_text: string;
  false_text: string;
}

const StatusLabel: React.FC<StatusLabelProps> = ({
  status,
  true_text,
  false_text,
}) => {
  return (
    <div
      className={`p-2 rounded-lg text-text-nemi text-sm ${status ? "bg-secondary-nemi" : "bg-bg-alt-nemi text-text-alt-nemi"}`}
    >
      <p
        className={`text-xs ${status ? "text-text-nemi" : "text-text-alt-nemi"}`}
      >
        {status ? true_text : false_text}
      </p>
    </div>
  );
};

export default StatusLabel;
