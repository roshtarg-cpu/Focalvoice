"use client";

import { ArrowLeft, Phone, Plus, Star, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import {
  createPhoneNumberApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersPost,
  deletePhoneNumberApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersPhoneNumberIdDelete,
  getTelephonyConfigurationByIdApiV1OrganizationsTelephonyConfigsConfigIdGet,
  listPhoneNumbersApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersGet,
} from "@/client/sdk.gen";
import type { PhoneNumberResponse, TelephonyConfigurationDetail } from "@/client/types.gen";
import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { detailFromError } from "@/lib/apiError";
import { useAuth } from "@/lib/auth";

export default function TelephonyConfigDetailPage() {
  const { configId } = useParams<{ configId: string }>();
  const router = useRouter();
  const { user, getAccessToken, loading: authLoading } = useAuth();

  const [config, setConfig] = useState<TelephonyConfigurationDetail | null>(null);
  const [numbers, setNumbers] = useState<PhoneNumberResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [newAddress, setNewAddress] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<PhoneNumberResponse | null>(null);
  const hasFetched = useRef(false);

  const numId = parseInt(configId, 10);

  const fetchData = useCallback(async () => {
    if (authLoading || !user) return;
    setLoading(true);
    try {
      const token = await getAccessToken();
      const headers = { Authorization: `Bearer ${token}` };

      const [cfgRes, numRes] = await Promise.all([
        getTelephonyConfigurationByIdApiV1OrganizationsTelephonyConfigsConfigIdGet({
          headers,
          path: { config_id: numId },
        }),
        listPhoneNumbersApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersGet({
          headers,
          path: { config_id: numId },
        }),
      ]);

      if (cfgRes.error) {
        toast.error(detailFromError(cfgRes.error, "Failed to load configuration"));
        router.push("/telephony-configurations");
        return;
      }
      setConfig(cfgRes.data ?? null);
      if (numRes.error) {
        toast.error(detailFromError(numRes.error, "Failed to load phone numbers"));
      } else {
        setNumbers(numRes.data?.phone_numbers ?? []);
      }
    } finally {
      setLoading(false);
    }
  }, [authLoading, user, getAccessToken, numId, router]);

  useEffect(() => {
    if (authLoading || !user || hasFetched.current) return;
    hasFetched.current = true;
    fetchData();
  }, [authLoading, user, fetchData]);

  const onAddNumber = async () => {
    if (!newAddress.trim()) return;
    setSaving(true);
    try {
      const token = await getAccessToken();
      const res = await createPhoneNumberApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersPost({
        headers: { Authorization: `Bearer ${token}` },
        path: { config_id: numId },
        body: { address: newAddress.trim(), label: newLabel.trim() || undefined },
      });
      if (res.error) {
        toast.error(detailFromError(res.error, "Failed to add phone number"));
        return;
      }
      toast.success("Phone number added");
      setAddOpen(false);
      setNewAddress("");
      setNewLabel("");
      hasFetched.current = false;
      fetchData();
    } finally {
      setSaving(false);
    }
  };

  const onConfirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      const token = await getAccessToken();
      const res = await deletePhoneNumberApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersPhoneNumberIdDelete({
        headers: { Authorization: `Bearer ${token}` },
        path: { config_id: numId, phone_number_id: deleteTarget.id },
      });
      if (res.error) {
        toast.error(detailFromError(res.error, "Failed to delete phone number"));
        return;
      }
      toast.success("Phone number removed");
      setDeleteTarget(null);
      hasFetched.current = false;
      fetchData();
    } catch {
      toast.error("Failed to delete phone number");
    }
  };

  return (
    <>
      <PageShell width="narrow">
        <div className="mb-4">
          <Link
            href="/telephony-configurations"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" /> Back to configurations
          </Link>
        </div>

        {loading ? (
          <div className="space-y-3">
            <Skeleton className="h-12 w-64" />
            <Skeleton className="h-24 w-full rounded-2xl" />
            <Skeleton className="h-24 w-full rounded-2xl" />
          </div>
        ) : (
          <>
            <PageHeader
              eyebrow={
                <span className="flex items-center gap-2">
                  <Badge variant="secondary">{config?.provider}</Badge>
                  {config?.is_default_outbound && (
                    <Badge className="gap-1">
                      <Star className="h-3 w-3 fill-current" /> Default
                    </Badge>
                  )}
                </span>
              }
              title={config?.name ?? "Telephony configuration"}
              subtitle={`ID: ${numId}`}
              actions={
                <Button onClick={() => setAddOpen(true)}>
                  <Plus className="h-4 w-4 mr-2" /> Add phone number
                </Button>
              }
            />

            {numbers.length === 0 ? (
              <EmptyState
                icon={Phone}
                title="No phone numbers yet"
                description="Add a phone number to this configuration to enable calls."
                action={
                  <Button onClick={() => setAddOpen(true)}>
                    <Plus className="h-4 w-4 mr-2" /> Add phone number
                  </Button>
                }
              />
            ) : (
              <div className="grid gap-3">
                {numbers.map((num) => (
                  <Card key={num.id} className="hover:border-border transition-colors">
                    <CardContent className="flex items-center gap-4 py-4">
                      <div className="flex flex-col gap-0.5 flex-1 min-w-0">
                        <span className="font-mono font-medium">{num.address_normalized || num.address}</span>
                        {num.label && (
                          <span className="text-sm text-muted-foreground">{num.label}</span>
                        )}
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge variant="outline" className="text-xs">{num.address_type}</Badge>
                          {num.country_code && (
                            <span className="text-xs text-muted-foreground">{num.country_code}</span>
                          )}
                          {num.is_default_caller_id && (
                            <Badge className="text-xs gap-1">
                              <Star className="h-2.5 w-2.5 fill-current" /> Default caller ID
                            </Badge>
                          )}
                          {num.inbound_workflow_name && (
                            <span className="text-xs text-muted-foreground">
                              Inbound: {num.inbound_workflow_name}
                            </span>
                          )}
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setDeleteTarget(num)}
                        title="Remove phone number"
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </>
        )}
      </PageShell>

      <Dialog open={addOpen} onOpenChange={(o) => { if (!o) { setNewAddress(""); setNewLabel(""); } setAddOpen(o); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add phone number</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="phone-address">Phone number *</Label>
              <Input
                id="phone-address"
                placeholder="+15551234567"
                value={newAddress}
                onChange={(e) => setNewAddress(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="phone-label">Label (optional)</Label>
              <Input
                id="phone-label"
                placeholder="e.g. US main line"
                value={newLabel}
                onChange={(e) => setNewLabel(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)} disabled={saving}>Cancel</Button>
            <Button onClick={onAddNumber} disabled={!newAddress.trim() || saving}>
              {saving ? "Adding…" : "Add"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove phone number?</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget?.address_normalized || deleteTarget?.address} will be removed from this
              configuration. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={onConfirmDelete}>Remove</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
