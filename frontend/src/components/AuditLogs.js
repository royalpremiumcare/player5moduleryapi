import React, { useState, useEffect } from "react";
import { format } from "date-fns";
import { tr, enGB } from "date-fns/locale";
import { FileText, Filter, User, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import api from "../api/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";

const AuditLogs = () => {
  const { t, i18n } = useTranslation();
  const dateLocale = i18n.language === "tr" ? tr : enGB;

  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    action: "",
    resource_type: "",
    user_id: "",
    start_date: "",
    end_date: "",
  });

  useEffect(() => {
    loadAuditLogs();
  }, []);

  const loadAuditLogs = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (filters.action) params.append("action", filters.action);
      if (filters.resource_type) params.append("resource_type", filters.resource_type);
      if (filters.user_id) params.append("user_id", filters.user_id);
      if (filters.start_date) params.append("start_date", filters.start_date);
      if (filters.end_date) params.append("end_date", filters.end_date);

      const response = await api.get(`/audit-logs?${params.toString()}`);
      setLogs(response.data);
    } catch (error) {
      console.error("Audit logs load failed:", error);
      toast.error(t("auditLogs.loadError"));
    } finally {
      setLoading(false);
    }
  };

  const getActionBadge = (action) => {
    const variants = {
      CREATE: {
        variant: "default",
        label: t("auditLogs.actionCreated"),
        className: "bg-green-500",
      },
      UPDATE: {
        variant: "secondary",
        label: t("auditLogs.actionUpdated"),
        className: "bg-blue-500 text-white",
      },
      DELETE: {
        variant: "destructive",
        label: t("auditLogs.actionDeleted"),
        className: "bg-red-500",
      },
    };
    const config = variants[action] || { variant: "outline", label: action, className: "" };
    return (
      <Badge variant={config.variant} className={config.className}>
        {config.label}
      </Badge>
    );
  };

  const getResourceTypeLabel = (type) => {
    const labels = {
      APPOINTMENT: t("auditLogs.resourceAppointment"),
      APPOINTMENT_BULK: t("auditLogs.resourceAppointmentBulk"),
      SETTINGS: t("auditLogs.resourceSettings"),
      CUSTOMER: t("auditLogs.resourceCustomer"),
      SERVICE: t("auditLogs.resourceService"),
      STAFF: t("auditLogs.resourceStaff"),
    };
    return labels[type] || type;
  };

  const formatTimestamp = (timestamp) => {
    try {
      const date = new Date(timestamp);
      return format(date, "dd MMM yyyy, HH:mm", { locale: dateLocale });
    } catch {
      return timestamp;
    }
  };

  const getChangesSummary = (log) => {
    if (log.action === "CREATE" && log.new_value?.kind === "bulk_session") {
      return t("auditLogs.summaryBulkSession", {
        count: log.new_value.session_count ?? 0,
        groupId: log.new_value.session_group_id || "—",
      });
    }
    if (log.action === "CREATE") {
      return t("auditLogs.summaryCreateGeneric");
    }
    if (log.action === "DELETE") {
      return t("auditLogs.summaryDelete");
    }
    if (log.action === "UPDATE" && log.new_value?.operation === "cancel_selected") {
      if (log.new_value.refund) {
        return t("auditLogs.summaryCancelRefund", {
          count: log.new_value.cancelled_count ?? 0,
          stripeId: log.new_value.stripe_refund_id || "—",
        });
      }
      return t("auditLogs.summaryCancelNoRefund", {
        count: log.new_value.cancelled_count ?? 0,
      });
    }
    if (log.action === "UPDATE" && log.old_value && log.new_value) {
      const changes = [];
      Object.keys(log.new_value).forEach((key) => {
        if (JSON.stringify(log.old_value[key]) !== JSON.stringify(log.new_value[key])) {
          changes.push(key);
        }
      });
      return changes.length > 0
        ? t("auditLogs.summaryUpdateFields", { fields: changes.join(", ") })
        : t("auditLogs.summaryUpdateGeneric");
    }
    if (log.action === "UPDATE") {
      return t("auditLogs.summaryUpdateGeneric");
    }
    return t("auditLogs.summaryChangedGeneric");
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <FileText className="h-6 w-6" />
          <h1 className="text-2xl font-bold">{t("auditLogs.title")}</h1>
        </div>
      </div>

      <Card className="p-4 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Filter className="h-5 w-5" />
          <h2 className="text-lg font-semibold">{t("auditLogs.filtersHeading")}</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
          <Select
            value={filters.action || "all"}
            onValueChange={(value) =>
              setFilters({ ...filters, action: value === "all" ? "" : value })
            }
          >
            <SelectTrigger>
              <SelectValue placeholder={t("auditLogs.actionType")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("auditLogs.filterAll")}</SelectItem>
              <SelectItem value="CREATE">{t("auditLogs.filterCreate")}</SelectItem>
              <SelectItem value="UPDATE">{t("auditLogs.filterUpdate")}</SelectItem>
              <SelectItem value="DELETE">{t("auditLogs.filterDelete")}</SelectItem>
            </SelectContent>
          </Select>

          <Select
            value={filters.resource_type || "all"}
            onValueChange={(value) =>
              setFilters({ ...filters, resource_type: value === "all" ? "" : value })
            }
          >
            <SelectTrigger>
              <SelectValue placeholder={t("auditLogs.resourceType")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("auditLogs.filterAll")}</SelectItem>
              <SelectItem value="APPOINTMENT">{t("auditLogs.resourceAppointment")}</SelectItem>
              <SelectItem value="APPOINTMENT_BULK">{t("auditLogs.resourceAppointmentBulk")}</SelectItem>
              <SelectItem value="SETTINGS">{t("auditLogs.resourceSettings")}</SelectItem>
              <SelectItem value="CUSTOMER">{t("auditLogs.resourceCustomer")}</SelectItem>
              <SelectItem value="SERVICE">{t("auditLogs.resourceService")}</SelectItem>
              <SelectItem value="STAFF">{t("auditLogs.resourceStaff")}</SelectItem>
            </SelectContent>
          </Select>

          <Input
            placeholder={t("auditLogs.userIdPlaceholder")}
            value={filters.user_id}
            onChange={(e) => setFilters({ ...filters, user_id: e.target.value })}
          />

          <Input
            type="date"
            placeholder={t("auditLogs.startDate")}
            value={filters.start_date}
            onChange={(e) => setFilters({ ...filters, start_date: e.target.value })}
          />

          <Input
            type="date"
            placeholder={t("auditLogs.endDate")}
            value={filters.end_date}
            onChange={(e) => setFilters({ ...filters, end_date: e.target.value })}
          />

          <button
            type="button"
            onClick={loadAuditLogs}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition h-10"
          >
            {t("auditLogs.filter")}
          </button>
        </div>
      </Card>

      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 mx-auto" />
          <p className="mt-4 text-gray-600">{t("auditLogs.loading")}</p>
        </div>
      ) : logs.length === 0 ? (
        <Card className="p-12 text-center">
          <AlertCircle className="h-12 w-12 mx-auto text-gray-400 mb-4" />
          <p className="text-gray-600">{t("auditLogs.empty")}</p>
        </Card>
      ) : (
        <div className="space-y-3">
          {logs.map((log) => (
            <Card key={log.id} className="p-4 hover:shadow-md transition">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    {getActionBadge(log.action)}
                    <Badge variant="outline">{getResourceTypeLabel(log.resource_type)}</Badge>
                    <span className="text-sm text-gray-500">{formatTimestamp(log.timestamp)}</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-gray-600 mb-1">
                    <User className="h-4 w-4" />
                    <span className="font-medium">{log.user_full_name}</span>
                    <span className="text-gray-400">({log.user_id})</span>
                  </div>
                  <p className="text-sm text-gray-700">{getChangesSummary(log)}</p>
                  {log.ip_address && (
                    <p className="text-xs text-gray-400 mt-1">
                      {t("auditLogs.ipLabel", { ip: log.ip_address })}
                    </p>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default AuditLogs;
