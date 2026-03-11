import { useState, useCallback, useMemo } from 'react';
import type { CampaignFormState } from '@/types/components';

interface CampaignFormErrors {
  name?: string;
  subject?: string;
  fromEmail?: string;
  fromName?: string;
  campaignListIds?: string;
  bodyHtml?: string;
}

/**
 * useCampaignForm hook - manage campaign form state and validation
 * Used in: CampaignBuilder and sub-components
 * 
 * Encapsulates:
 * - Form field state
 * - Field-level validation
 * - Step completion validation
 * - Draft auto-save preparation
 * - Form reset
 * 
 * @example
 * const form = useCampaignForm();
 * form.setField('name', 'My Campaign');
 * if (form.canProceedStep(1)) { ... }
 */
export const useCampaignForm = (initialValues?: Partial<CampaignFormState>) => {
  const [form, setForm] = useState<CampaignFormState>({
    name: '',
    subject: '',
    previewText: '',
    fromEmail: '',
    fromName: '',
    replyTo: '',
    templateId: null,
    bodyHtml: '',
    bodyText: '',
    campaignListIds: [],
    segmentId: undefined,
    tagIds: [],
    trackingOpens: false,
    trackingClicks: false,
    timewarp: false,
    gaTag: undefined,
    ...initialValues,
  });

  const [errors, setErrors] = useState<CampaignFormErrors>({});

  const setField = useCallback(<K extends keyof CampaignFormState>(
    key: K,
    value: CampaignFormState[K]
  ) => {
    setForm(prev => ({
      ...prev,
      [key]: value,
    }));
    // Clear error for this field when user starts typing
    if (errors[key as keyof CampaignFormErrors]) {
      setErrors(prev => ({
        ...prev,
        [key]: undefined,
      }));
    }
  }, [errors]);

  const updateFields = useCallback((updates: Partial<CampaignFormState>) => {
    setForm(prev => ({
      ...prev,
      ...updates,
    }));
  }, []);

  const validate = useCallback((): CampaignFormErrors => {
    const newErrors: CampaignFormErrors = {};

    if (!form.name?.trim()) {
      newErrors.name = 'Campaign name is required';
    }

    if (!form.subject?.trim()) {
      newErrors.subject = 'Subject line is required';
    } else if (form.subject.length > 100) {
      newErrors.subject = 'Subject line must be 100 characters or less';
    }

    if (!form.fromEmail?.trim()) {
      newErrors.fromEmail = 'From email is required';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.fromEmail)) {
      newErrors.fromEmail = 'Invalid email format';
    }

    if (!form.fromName?.trim()) {
      newErrors.fromName = 'From name is required';
    }

    if (form.campaignListIds.length === 0) {
      newErrors.campaignListIds = 'At least one campaign list is required';
    }

    if (!form.bodyHtml?.trim()) {
      newErrors.bodyHtml = 'Email body is required';
    }

    setErrors(newErrors);
    return newErrors;
  }, [form]);

  const canProceedStep1 = useMemo(() => {
    return form.name?.trim() && form.subject?.trim();
  }, [form.name, form.subject]);

  const canProceedStep2 = useMemo(() => {
    return form.campaignListIds.length > 0;
  }, [form.campaignListIds]);

  const canProceedStep3 = useMemo(() => {
    return form.bodyHtml?.trim() || form.bodyText?.trim();
  }, [form.bodyHtml, form.bodyText]);

  const canProceedStep4 = useMemo(() => {
    return true; // tracking is optional
  }, []);

  const canProceedStep5 = useMemo(() => {
    const errs = validate();
    return Object.keys(errs).length === 0;
  }, [validate]);

  const reset = useCallback(() => {
    setForm({
      name: '',
      subject: '',
      previewText: '',
      fromEmail: '',
      fromName: '',
      replyTo: '',
      templateId: null,
      bodyHtml: '',
      bodyText: '',
      campaignListIds: [],
      segmentId: undefined,
      tagIds: [],
      trackingOpens: false,
      trackingClicks: false,
      timewarp: false,
      gaTag: undefined,
    });
    setErrors({});
  }, []);

  const getDraft = useCallback(() => {
    return { ...form };
  }, [form]);

  return {
    form,
    setField,
    updateFields,
    errors,
    validate,
    reset,
    getDraft,
    canProceedStep1,
    canProceedStep2,
    canProceedStep3,
    canProceedStep4,
    canProceedStep5,
  };
};

export default useCampaignForm;
