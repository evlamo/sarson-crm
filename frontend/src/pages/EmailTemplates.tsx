import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Plus, Edit, Trash2 } from "lucide-react";
import { apiClient } from "@/lib/api-client";

interface EmailTemplate {
  id: string;
  name: string;
  description: string | null;
  thumbnail_url: string | null;
  is_mailchimp_template: boolean;
  created_at: string;
}

export function EmailTemplates() {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    try {
      const response = await apiClient.get("/email-templates");
      setTemplates(response.data.data || []);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this template?")) return;

    await apiClient.delete(`/email-templates/${id}`);
    loadTemplates();
  };

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Email Templates</h1>
        <Button onClick={() => navigate("/email-templates/new")}>
          <Plus className="w-4 h-4 mr-2" />
          New Template
        </Button>
      </div>

      {loading ? (
        <p>Loading templates...</p>
      ) : templates.length === 0 ? (
        <Card className="p-12 text-center">
          <p className="text-muted-foreground mb-4">No templates yet</p>
          <Button onClick={() => navigate("/email-templates/new")}>
            Create Your First Template
          </Button>
        </Card>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {templates.map((template) => (
            <Card key={template.id} className="p-4">
              {template.thumbnail_url && (
                <img
                  src={template.thumbnail_url}
                  alt={template.name}
                  className="w-full h-32 object-cover rounded mb-2"
                />
              )}
              <h3 className="font-semibold">{template.name}</h3>
              {template.description && (
                <p className="text-sm text-muted-foreground mb-2">
                  {template.description}
                </p>
              )}
              <div className="flex gap-2 mt-4">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => navigate(`/email-templates/${template.id}`)}
                >
                  <Edit className="w-4 h-4" />
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => handleDelete(template.id)}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
