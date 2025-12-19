import { useState, useEffect } from "react";
import { ArrowLeft, Plus, Trash2, Edit2, DollarSign, TrendingUp, TrendingDown, Calendar, X } from "lucide-react";
import { toast } from "sonner";
import api from "../api/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { format } from "date-fns";
import { tr, enGB } from "date-fns/locale";
import { useTranslation } from "react-i18next";
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

const Finance = ({ onNavigate }) => {
  const { t, i18n } = useTranslation();
  const dateLocale = i18n.language === 'tr' ? tr : enGB;
  const [activeTab, setActiveTab] = useState("summary");
  const [period, setPeriod] = useState("this_month");
  const [summary, setSummary] = useState(null);
  const [expenses, setExpenses] = useState([]);
  const [payroll, setPayroll] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showExpenseDialog, setShowExpenseDialog] = useState(false);
  const [showPaymentDialog, setShowPaymentDialog] = useState(false);
  const [selectedStaff, setSelectedStaff] = useState(null);
  const [deleteExpenseId, setDeleteExpenseId] = useState(null);
  const [expenseForm, setExpenseForm] = useState({
    title: "",
    amount: "",
    category: i18n.language === 'tr' ? "Diğer" : "Other",
    date: format(new Date(), "yyyy-MM-dd")
  });
  const [paymentForm, setPaymentForm] = useState({
    amount: "",
    date: format(new Date(), "yyyy-MM-dd")
  });

  const expenseCategories = i18n.language === 'tr' 
    ? [t('finance.management.expenses.categories.bill'), t('finance.management.expenses.categories.rent'), t('finance.management.expenses.categories.material'), t('finance.management.expenses.categories.staffPayment'), t('finance.management.expenses.categories.other')]
    : [t('finance.management.expenses.categories.bill'), t('finance.management.expenses.categories.rent'), t('finance.management.expenses.categories.material'), t('finance.management.expenses.categories.staffPayment'), t('finance.management.expenses.categories.other')];

  useEffect(() => {
    loadData();
  }, [activeTab, period]);

  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === "summary") {
        const response = await api.get(`/finance/summary?period=${period}`);
        setSummary(response.data);
      } else if (activeTab === "expenses") {
        const response = await api.get("/expenses");
        setExpenses(response.data || []);
      } else if (activeTab === "payroll") {
        const response = await api.get(`/finance/payroll?period=${period}`);
        setPayroll(response.data);
      }
    } catch (error) {
      toast.error(t('finance.management.loadingError'));
    } finally {
      setLoading(false);
    }
  };

  const handleAddExpense = async () => {
    if (!expenseForm.title || !expenseForm.amount || !expenseForm.date) {
      toast.error(t('finance.management.fillAllFields'));
      return;
    }

    try {
      await api.post("/expenses", {
        title: expenseForm.title,
        amount: parseFloat(expenseForm.amount),
        category: expenseForm.category,
        date: expenseForm.date
      });
      toast.success(t('finance.management.expenseAdded'));
      setShowExpenseDialog(false);
      setExpenseForm({ title: "", amount: "", category: i18n.language === 'tr' ? "Diğer" : "Other", date: format(new Date(), "yyyy-MM-dd") });
      // Verileri yeniden yükle
      setLoading(true);
      try {
        if (activeTab === "summary") {
          const summaryResponse = await api.get(`/finance/summary?period=${period}`);
          setSummary(summaryResponse.data);
        }
        if (activeTab === "expenses") {
          const expensesResponse = await api.get("/expenses");
          setExpenses(expensesResponse.data || []);
        }
      } catch (error) {
        console.error("Data reload error:", error);
      } finally {
        setLoading(false);
      }
    } catch (error) {
      toast.error(t('finance.management.expenseAddError'));
    }
  };

  const handleDeleteExpense = async () => {
    if (!deleteExpenseId) return;

    try {
      await api.delete(`/expenses/${deleteExpenseId}`);
      toast.success(t('finance.management.expenseDeleted'));
      setDeleteExpenseId(null);
      await loadData();
      if (activeTab === "summary") {
        const response = await api.get(`/finance/summary?period=${period}`);
        setSummary(response.data);
      }
    } catch (error) {
      toast.error(t('finance.management.expenseDeleteError'));
    }
  };

  const handleMakePayment = async () => {
    if (!selectedStaff || !paymentForm.amount) {
      toast.error(t('finance.management.enterAmount'));
      return;
    }

    try {
      const response = await api.post("/finance/payroll/payment", {
        staff_username: selectedStaff.username,
        amount: parseFloat(paymentForm.amount),
        date: paymentForm.date
      });
      console.log("Payment response:", response.data);
      toast.success(t('finance.management.paymentSaved'));
      setShowPaymentDialog(false);
      setSelectedStaff(null);
      setPaymentForm({ amount: "", date: format(new Date(), "yyyy-MM-dd") });
      // Verileri yeniden yükle
      setLoading(true);
      try {
        if (activeTab === "summary") {
          const summaryResponse = await api.get(`/finance/summary?period=${period}`);
          setSummary(summaryResponse.data);
        }
        if (activeTab === "expenses") {
          const expensesResponse = await api.get("/expenses");
          setExpenses(expensesResponse.data || []);
        }
        if (activeTab === "payroll") {
          const payrollResponse = await api.get(`/finance/payroll?period=${period}`);
          setPayroll(payrollResponse.data);
        }
      } catch (error) {
        console.error("Data reload error:", error);
      } finally {
        setLoading(false);
      }
    } catch (error) {
      console.error("Payment error:", error);
      const errorMessage = error.response?.data?.detail || error.message || t('finance.management.paymentSaveError');
      toast.error(errorMessage);
    }
  };

  return (
    <div className="space-y-4 pb-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => onNavigate && onNavigate("settings")}
          className="flex items-center gap-2 px-3 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
          <span className="text-sm font-medium">{t('settings.backToSettings')}</span>
        </button>
      </div>

      <div>
        <h2 className="text-2xl font-bold text-gray-900">{t('finance.management.title')}</h2>
        <p className="text-sm text-gray-600 mt-1">{t('finance.management.subtitle')}</p>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="summary">{t('finance.management.tabs.summary')}</TabsTrigger>
          <TabsTrigger value="expenses">{t('finance.management.tabs.expenses')}</TabsTrigger>
          <TabsTrigger value="payroll">{t('finance.management.tabs.payroll')}</TabsTrigger>
        </TabsList>

        {/* SEKME 1: Özet */}
        <TabsContent value="summary" className="space-y-4">
          {/* Tarih Filtresi */}
          <div className="flex flex-wrap gap-2">
            <Button
              variant={period === "today" ? "default" : "outline"}
              size="sm"
              onClick={() => setPeriod("today")}
            >
              {t('finance.management.periods.today')}
            </Button>
            <Button
              variant={period === "this_month" ? "default" : "outline"}
              size="sm"
              onClick={() => setPeriod("this_month")}
            >
              {t('finance.management.periods.thisMonth')}
            </Button>
            <Button
              variant={period === "last_month" ? "default" : "outline"}
              size="sm"
              onClick={() => setPeriod("last_month")}
            >
              {t('finance.management.periods.lastMonth')}
            </Button>
            <Button
              variant={period === "this_year" ? "default" : "outline"}
              size="sm"
              onClick={() => setPeriod("this_year")}
            >
              {t('finance.management.periods.thisYear')}
            </Button>
          </div>

          {loading ? (
            <Card className="p-8 text-center">
              <p className="text-gray-500">{t('common.loading')}</p>
            </Card>
          ) : summary ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Toplam Gelir */}
              <Card className="p-6 bg-gradient-to-br from-green-50 to-green-100 border-green-200">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-green-700 font-medium mb-1">{t('finance.management.summary.totalRevenue')}</p>
                    <p className="text-3xl font-bold text-green-900">
                      {Math.round(summary.total_revenue || 0).toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB')} {i18n.language === 'tr' ? '₺' : '£'}
                    </p>
                  </div>
                  <TrendingUp className="w-10 h-10 text-green-600" />
                </div>
              </Card>

              {/* Toplam Gider */}
              <Card className="p-6 bg-gradient-to-br from-red-50 to-red-100 border-red-200">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-red-700 font-medium mb-1">{t('finance.management.summary.totalExpenses')}</p>
                    <p className="text-3xl font-bold text-red-900">
                      {Math.round(summary.total_expenses || 0).toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB')} {i18n.language === 'tr' ? '₺' : '£'}
                    </p>
                  </div>
                  <TrendingDown className="w-10 h-10 text-red-600" />
                </div>
              </Card>

              {/* Net Kâr */}
              <Card className={`p-6 bg-gradient-to-br ${summary.net_profit >= 0 ? 'from-blue-50 to-blue-100 border-blue-200' : 'from-gray-50 to-gray-100 border-gray-200'}`}>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium mb-1" style={{ color: summary.net_profit >= 0 ? '#1e40af' : '#374151' }}>
                      {t('finance.management.summary.netProfit')}
                    </p>
                    <p className={`text-3xl font-bold ${summary.net_profit >= 0 ? 'text-blue-900' : 'text-gray-900'}`}>
                      {Math.round(summary.net_profit || 0).toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB')} {i18n.language === 'tr' ? '₺' : '£'}
                    </p>
                  </div>
                </div>
              </Card>
            </div>
          ) : null}
          
          {/* Personel Kazançları */}
          {summary?.staff_earnings?.length > 0 && (
            <Card className="p-4 mt-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">
                {period === "today" && t('finance.management.summary.staffEarnings.today')}
                {period === "this_month" && t('finance.management.summary.staffEarnings.thisMonth')}
                {period === "last_month" && t('finance.management.summary.staffEarnings.lastMonth')}
                {period === "this_year" && t('finance.management.summary.staffEarnings.thisYear')}
              </h3>
              <div className="flex flex-wrap gap-2">
                {summary.staff_earnings.map((staff) => (
                  <div
                    key={staff.username}
                    className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 border border-gray-200 rounded-lg text-sm"
                  >
                    <span className="font-medium text-gray-900">{staff.full_name}</span>
                    <span className="font-bold text-green-600">{Math.round(staff.total).toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB')}{i18n.language === 'tr' ? '₺' : '£'}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </TabsContent>

        {/* SEKME 2: Giderler */}
        <TabsContent value="expenses" className="space-y-4">
          {loading ? (
            <Card className="p-8 text-center">
              <p className="text-gray-500">{t('common.loading')}</p>
            </Card>
          ) : (
            <>
              <div className="space-y-3">
                {expenses.length === 0 ? (
                  <Card className="p-8 text-center">
                    <p className="text-gray-500">{t('finance.management.expenses.noExpenses')}</p>
                  </Card>
                ) : (
                  expenses.map((expense) => (
                    <Card key={expense.id} className="p-4 bg-white rounded-xl shadow-sm border border-gray-100">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <h3 className="font-semibold text-gray-900">{expense.title}</h3>
                          <div className="flex items-center gap-4 mt-1">
                            <span className="text-sm text-gray-600">
                              {format(new Date(expense.date), "d MMMM yyyy", { locale: dateLocale })}
                            </span>
                            <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs">
                              {expense.category}
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-lg font-bold text-red-600">
                            {expense.amount?.toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || 0} {i18n.language === 'tr' ? '₺' : '£'}
                          </span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setDeleteExpenseId(expense.id)}
                            className="text-red-600 hover:text-red-700"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    </Card>
                  ))
                )}
              </div>

              {/* FAB: Gider Ekle */}
              <div className="fixed bottom-20 right-4 z-50">
                <Button
                  onClick={() => setShowExpenseDialog(true)}
                  className="w-14 h-14 rounded-full bg-blue-600 hover:bg-blue-700 shadow-lg"
                >
                  <Plus className="w-6 h-6" />
                </Button>
              </div>
            </>
          )}
        </TabsContent>

        {/* SEKME 3: Personel */}
        <TabsContent value="payroll" className="space-y-4">
          {/* Tarih Filtresi */}
          <div className="flex gap-2">
            <Button
              variant={period === "this_month" ? "default" : "outline"}
              size="sm"
              onClick={() => setPeriod("this_month")}
            >
              {t('finance.management.periods.thisMonth')}
            </Button>
            <Button
              variant={period === "last_month" ? "default" : "outline"}
              size="sm"
              onClick={() => setPeriod("last_month")}
            >
              {t('finance.management.periods.lastMonth')}
            </Button>
          </div>

          {loading ? (
            <Card className="p-8 text-center">
              <p className="text-gray-500">{t('common.loading')}</p>
            </Card>
          ) : payroll && payroll.payroll ? (
            <div className="space-y-3">
              {payroll.payroll.length === 0 ? (
                <Card className="p-8 text-center">
                  <p className="text-gray-500">{t('finance.management.payroll.noStaff')}</p>
                </Card>
              ) : (
                payroll.payroll.map((staff) => (
                  <Card key={staff.username} className="p-4 bg-white rounded-xl shadow-sm border border-gray-100">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <h3 className="font-semibold text-gray-900">{staff.full_name}</h3>
                        <p className="text-sm text-gray-600">
                          {staff.payment_type === "salary" 
                            ? `${t('finance.management.payroll.fixedSalary')} - ${staff.payment_amount?.toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB') || 0} ${i18n.language === 'tr' ? '₺' : '£'}`
                            : `${t('finance.management.payroll.commission')} - %${staff.payment_amount || 0}`
                          }
                        </p>
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-3 mb-3">
                      <div>
                        <p className="text-xs text-gray-600 mb-1">{t('finance.management.payroll.earned')}</p>
                        <p className="text-lg font-bold text-green-600">
                          {staff.earned?.toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || 0} {i18n.language === 'tr' ? '₺' : '£'}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-600 mb-1">{t('finance.management.payroll.paid')}</p>
                        <p className="text-lg font-bold text-blue-600">
                          {staff.paid?.toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || 0} {i18n.language === 'tr' ? '₺' : '£'}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-600 mb-1">{t('finance.management.payroll.balance')}</p>
                        <p className={`text-lg font-bold ${staff.balance >= 0 ? 'text-gray-900' : 'text-red-600'}`}>
                          {staff.balance?.toLocaleString(i18n.language === 'tr' ? 'tr-TR' : 'en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || 0} {i18n.language === 'tr' ? '₺' : '£'}
                        </p>
                      </div>
                    </div>
                    <Button
                      onClick={() => {
                        setSelectedStaff(staff);
                        setShowPaymentDialog(true);
                      }}
                      className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg"
                    >
                      {t('finance.management.payroll.makePayment')}
                    </Button>
                  </Card>
                ))
              )}
            </div>
          ) : null}
        </TabsContent>
      </Tabs>

      {/* Gider Ekleme Dialog */}
      <Dialog open={showExpenseDialog} onOpenChange={setShowExpenseDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('finance.management.expenses.addTitle')}</DialogTitle>
            <DialogDescription>
              {t('finance.management.expenses.addDescription')}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="expense_title">{t('finance.management.expenses.fields.title')} *</Label>
              <Input
                id="expense_title"
                value={expenseForm.title}
                onChange={(e) => setExpenseForm({ ...expenseForm, title: e.target.value })}
                placeholder={t('finance.management.expenses.fields.titlePlaceholder')}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="expense_amount">{t('finance.management.expenses.fields.amount')} *</Label>
              <Input
                id="expense_amount"
                type="number"
                min="0"
                step="0.01"
                value={expenseForm.amount}
                onChange={(e) => setExpenseForm({ ...expenseForm, amount: e.target.value })}
                placeholder="0.00"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="expense_category">{t('finance.management.expenses.fields.category')} *</Label>
              <Select
                value={expenseForm.category}
                onValueChange={(value) => setExpenseForm({ ...expenseForm, category: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {expenseCategories.map((cat) => (
                    <SelectItem key={cat} value={cat}>{cat}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="expense_date">{t('finance.management.expenses.fields.date')} *</Label>
              <Input
                id="expense_date"
                type="date"
                value={expenseForm.date}
                onChange={(e) => setExpenseForm({ ...expenseForm, date: e.target.value })}
              />
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => setShowExpenseDialog(false)}
              className="flex-1"
            >
              {t('common.cancel')}
            </Button>
            <Button
              onClick={handleAddExpense}
              className="flex-1 bg-blue-600 hover:bg-blue-700"
            >
              {t('common.save')}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Ödeme Yapma Dialog */}
      <Dialog open={showPaymentDialog} onOpenChange={setShowPaymentDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('finance.management.payroll.paymentTitle', { name: selectedStaff?.full_name })}</DialogTitle>
            <DialogDescription>
              {t('finance.management.payroll.paymentDescription')}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="payment_amount">{t('finance.management.payroll.paymentAmount')} *</Label>
              <Input
                id="payment_amount"
                type="number"
                min="0"
                step="0.01"
                value={paymentForm.amount}
                onChange={(e) => setPaymentForm({ ...paymentForm, amount: e.target.value })}
                placeholder="0.00"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="payment_date">{t('finance.management.payroll.paymentDate')} *</Label>
              <Input
                id="payment_date"
                type="date"
                value={paymentForm.date}
                onChange={(e) => setPaymentForm({ ...paymentForm, date: e.target.value })}
              />
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setShowPaymentDialog(false);
                setSelectedStaff(null);
              }}
              className="flex-1"
            >
              {t('common.cancel')}
            </Button>
            <Button
              onClick={handleMakePayment}
              className="flex-1 bg-blue-600 hover:bg-blue-700"
            >
              {t('common.save')}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Gider Silme Onay Dialog */}
      <AlertDialog open={!!deleteExpenseId} onOpenChange={() => setDeleteExpenseId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('finance.management.expenses.deleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('finance.management.expenses.deleteDescription')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteExpense}
              className="bg-red-500 hover:bg-red-600"
            >
              {t('common.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default Finance;

