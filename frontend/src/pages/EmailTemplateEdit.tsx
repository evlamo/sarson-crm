import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { EmailTemplateEditor } from "@/components/email-templates/EmailTemplateEditor";
import { apiClient } from "@/lib/api-client";

export function EmailTemplateEdit() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [initialDesign, setInitialDesign] = useState<Record<string, any> | undefined>();
  const [initialName, setInitialName] = useState("");
  const [initialDescription, setInitialDescription] = useState("");
  const [loading, setLoading] = useState(!!id);

  useEffect(() => {
    if (id) {
      loadTemplate();
    }
  }, [id]);

  const loadTemplate = async () => {
    try {
      const response = await apiClient.get(`/email-templates/${id}`);
      const template = response.data.data;
      setInitialDesign(template.design_json);
      setInitialName(template.name);
      setInitialDescription(template.description || "");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (data: {
    name: string;
    description: string;
    design: Record<string, any>;
    html: string;
  }) => {
    const payload = {
      name: data.name,
      description: data.description,
      design_json: data.design,
      html: data.html,
    };

    if (id) {
      await apiClient.patch(`/email-templates/${id}`, payload);
    } else {
      await apiClient.post("/email-templates", payload);
    }

    navigate("/email-templates");
  };

  if (loading) {
    return <div className="p-6">Loading...</div>;
  }

  return (
    <EmailTemplateEditor
      templateId={id}
      initialDesign={initialDesign}
      initialName={initialName}
      initialDescription={initialDescription}
      onSave={handleSave}
    />
  );
}
