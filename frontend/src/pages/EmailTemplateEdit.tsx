import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "@tanstack/react-router";
import { EmailTemplateEditor } from "@/components/email-templates/EmailTemplateEditor";
import api from "@/lib/api";

export function EmailTemplateEdit() {
  const params = useParams({ strict: false }) as { id?: string };
  const navigate = useNavigate();
  const [initialDesign, setInitialDesign] = useState<Record<string, any> | undefined>();
  const [initialName, setInitialName] = useState("");
  const [initialDescription, setInitialDescription] = useState("");
  const [loading, setLoading] = useState(!!params.id);

  useEffect(() => {
    if (params.id) {
      loadTemplate();
    }
  }, [params.id]);

  const loadTemplate = async () => {
    try {
      const response = await api.get(`/email-templates/${params.id}`);
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

    if (params.id) {
      await api.patch(`/email-templates/${params.id}`, payload);
    } else {
      await api.post("/email-templates", payload);
    }

    navigate({ to: "/email-templates" });
  };

  if (loading) {
    return <div className="p-6">Loading...</div>;
  }

  return (
    <EmailTemplateEditor
      templateId={params.id}
      initialDesign={initialDesign}
      initialName={initialName}
      initialDescription={initialDescription}
      onSave={handleSave}
    />
  );
}
