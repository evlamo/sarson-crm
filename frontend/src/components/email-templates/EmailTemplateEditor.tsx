import React, { useRef, useState, useEffect } from "react";
// Note: Install react-email-editor via: npm install react-email-editor
// import EmailEditor, { EditorRef, Design } from "react-email-editor";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Save, Eye, Download } from "lucide-react";

interface EmailTemplateEditorProps {
  templateId?: string;
  initialDesign?: Record<string, any>;
  initialName?: string;
  initialDescription?: string;
  onSave: (data: {
    name: string;
    description: string;
    design: Record<string, any>;
    html: string;
  }) => Promise<void>;
}

export function EmailTemplateEditor({
  templateId,
  initialDesign,
  initialName = "",
  initialDescription = "",
  onSave,
}: EmailTemplateEditorProps) {
  const [name, setName] = useState(initialName);
  const [description, setDescription] = useState(initialDescription);
  const [saving, setSaving] = useState(false);
  const [htmlContent, setHtmlContent] = useState("");

  useEffect(() => {
    if (initialDesign) {
      // Design would be loaded here
    }
  }, [initialDesign]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave({
        name,
        description,
        design: initialDesign || {},
        html: htmlContent,
      });
    } finally {
      setSaving(false);
    }
  };

  const handlePreview = () => {
    if (htmlContent) {
      const previewWindow = window.open("", "_blank");
      if (previewWindow) {
        previewWindow.document.write(htmlContent);
        previewWindow.document.close();
      }
    }
  };

  const handleDownloadHTML = () => {
    if (htmlContent) {
      const blob = new Blob([htmlContent], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${name || "template"}.html`;
      a.click();
      URL.revokeObjectURL(url);
    }
  };

  return (
    <div className="flex flex-col h-screen">
      <Card className="p-4 mb-4">
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <Label htmlFor="template-name">Template Name</Label>
            <Input
              id="template-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Email Template"
            />
          </div>
          <div>
            <Label htmlFor="template-description">Description</Label>
            <Textarea
              id="template-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
              rows={1}
            />
          </div>
        </div>

        <div className="flex gap-2">
          <Button onClick={handleSave} disabled={saving || !name}>
            <Save className="w-4 h-4 mr-2" />
            {saving ? "Saving..." : "Save Template"}
          </Button>
          <Button onClick={handlePreview} variant="outline">
            <Eye className="w-4 h-4 mr-2" />
            Preview
          </Button>
          <Button onClick={handleDownloadHTML} variant="outline">
            <Download className="w-4 h-4 mr-2" />
            Download HTML
          </Button>
        </div>
      </Card>

      <div className="flex-1 border rounded-lg overflow-hidden bg-gray-50 p-4">
        <p className="text-gray-500">
          Email editor placeholder. After npm install react-email-editor, uncomment editor.
        </p>
      </div>
    </div>
  );
}
