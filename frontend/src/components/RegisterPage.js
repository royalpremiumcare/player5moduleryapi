import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Building2, User, Mail, Lock, ArrowRight, Phone, Globe, MessageCircle, ArrowLeft } from 'lucide-react';
import { toast, Toaster } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardHeader, CardContent, CardTitle, CardDescription } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import posthog from '../lib/posthog';
import metaPixel from '../lib/metaPixel';

const RegisterPage = () => { 
    const navigate = useNavigate();
    const { register, registerVerify } = useAuth(); 
    const { t, i18n } = useTranslation();

    useEffect(() => { window.scrollTo(0, 0); }, []);

    // Dil bazlı telefon numarası başlangıcı - useEffect ile güncelle
    useEffect(() => {
        const savedLang = localStorage.getItem('i18nextLng');
        const browserLang = navigator.language || navigator.userLanguage;
        const isEnglish = savedLang === 'en' || (!savedLang && browserLang && !browserLang.startsWith('tr'));
        const prefix = isEnglish ? '+44' : '+90';
        
        // Eğer mevcut telefon numarası diğer prefix ile başlıyorsa, yeni prefix ile değiştir
        setFormData(prev => {
            if (!prev.support_phone.startsWith(prefix)) {
                return { ...prev, support_phone: prefix };
            }
            return prev;
        });
    }, [i18n.language]);

    const [formData, setFormData] = useState({
        username: '',
        password: '',
        full_name: '',
        organization_name: '',
        support_phone: i18n.language === 'en' ? '+44' : '+90',
        sector: ''
    });
    const [loading, setLoading] = useState(false);
    const [signupStartedTracked, setSignupStartedTracked] = useState(false);

    // OTP / verification state
    const [step, setStep] = useState('form'); // 'form' | 'otp'
    const [otpCode, setOtpCode] = useState('');
    const [phoneMasked, setPhoneMasked] = useState('');
    const [otpExpiresAt, setOtpExpiresAt] = useState(null);
    const [resendCooldown, setResendCooldown] = useState(0);
    const [secondsLeft, setSecondsLeft] = useState(0);
    const otpInputRef = useRef(null);

    // OTP TTL countdown
    useEffect(() => {
        if (!otpExpiresAt) return undefined;
        const tick = () => {
            const remaining = Math.max(0, Math.floor((otpExpiresAt - Date.now()) / 1000));
            setSecondsLeft(remaining);
        };
        tick();
        const id = setInterval(tick, 1000);
        return () => clearInterval(id);
    }, [otpExpiresAt]);

    // Resend cooldown countdown
    useEffect(() => {
        if (resendCooldown <= 0) return undefined;
        const id = setInterval(() => {
            setResendCooldown((s) => Math.max(0, s - 1));
        }, 1000);
        return () => clearInterval(id);
    }, [resendCooldown]);

    // OTP step'e geçince input'a focus
    useEffect(() => {
        if (step === 'otp' && otpInputRef.current) {
            setTimeout(() => otpInputRef.current?.focus(), 100);
        }
    }, [step]);

    // Funnel: signup_form_started — kullanıcı ilk kez bir input'a etkileşim ettiğinde
    const handleFormFocus = () => {
        if (signupStartedTracked) return;
        setSignupStartedTracked(true);
        try { posthog.track('signup_form_started'); } catch (_) {}
    };

    const formatSecs = (s) => {
        const m = Math.floor(s / 60);
        const ss = s % 60;
        return `${m}:${String(ss).padStart(2, '0')}`;
    };

    const [isAppMode, setIsAppMode] = useState(() => {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('mode') === 'app') {
            localStorage.setItem('is_app_mode', 'true');
            return true;
        }
        return localStorage.getItem('is_app_mode') === 'true';
    });

    const handleChange = (e) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };
    
    const handlePhoneChange = (e) => {
        let value = e.target.value;
        const isEnglish = i18n.language === 'en';
        const prefix = isEnglish ? '+44' : '+90';
        const maxLength = isEnglish ? 14 : 13; // +44XXXXXXXXXX (14) vs +90XXXXXXXXX (13)
        
        if (!value.startsWith(prefix)) {
            value = prefix + value.replace(/^\+?[0-9]*/, '');
        }
        value = value.replace(/[^0-9+]/g, '');
        if (value.length > maxLength) {
            value = value.substring(0, maxLength);
        }
        setFormData({ ...formData, support_phone: value });
    };

    // 1. ADIM: Form submit → /register-initiate (WhatsApp OTP gönder)
    const handleRegister = async (e) => {
        e.preventDefault();
        setLoading(true);

        try {
            const result = await register(
                formData.username,
                formData.password,
                formData.full_name,
                formData.organization_name,
                formData.support_phone,
                formData.sector
            );

            if (result.success && result.verificationRequired) {
                setPhoneMasked(result.phoneMasked || '');
                setOtpExpiresAt(Date.now() + (result.expiresIn || 900) * 1000);
                setResendCooldown(60); // 60sn flood koruması
                setOtpCode('');
                setStep('otp');
                toast.success(t('auth.register.otpSent', 'Doğrulama kodu WhatsApp\'a gönderildi.'));
            } else {
                toast.error(result.error || t('auth.register.error'));
            }
        } catch (error) {
            toast.error(t('auth.register.error'));
        } finally {
            setLoading(false);
        }
    };

    // 2. ADIM: OTP submit → /register-verify (hesap oluşur, otomatik login)
    const handleVerify = async (e) => {
        if (e && e.preventDefault) e.preventDefault();
        if (!/^\d{6}$/.test(otpCode)) {
            toast.error(t('auth.register.otpInvalid', 'Lütfen 6 haneli kodu girin.'));
            return;
        }
        setLoading(true);
        try {
            const result = await registerVerify(formData.support_phone, otpCode, formData.sector);
            if (result.success) {
                toast.success(t('auth.register.success'));

                // Meta: CompleteRegistration — OTP doğrulandı, hesap oluştu.
                try {
                    metaPixel.track('CompleteRegistration', {
                        customData: {
                            content_name: formData.organization_name || 'PLANN',
                            content_category: 'registration',
                            status: 'completed',
                        },
                        userData: {
                            contact_email: formData.username,
                            contact_phone: formData.support_phone,
                            contact_name: formData.full_name,
                        },
                    });
                } catch (_) {}

                // Auto-login içinde token kaydedildi → AppRouter dashboard'a yönlendirir
                navigate('/');
            } else {
                toast.error(result.error || t('auth.register.otpError', 'Kod hatalı veya süresi dolmuş.'));
            }
        } catch (error) {
            toast.error(t('auth.register.otpError', 'Doğrulama sırasında hata oluştu.'));
        } finally {
            setLoading(false);
        }
    };

    // OTP yeniden gönder
    const handleResend = async () => {
        if (resendCooldown > 0 || loading) return;
        setLoading(true);
        try {
            const result = await register(
                formData.username,
                formData.password,
                formData.full_name,
                formData.organization_name,
                formData.support_phone,
                formData.sector
            );
            if (result.success && result.verificationRequired) {
                setOtpExpiresAt(Date.now() + (result.expiresIn || 900) * 1000);
                setResendCooldown(60);
                setOtpCode('');
                toast.success(t('auth.register.otpResent', 'Yeni kod gönderildi.'));
            } else {
                toast.error(result.error || t('auth.register.error'));
            }
        } catch (error) {
            toast.error(t('auth.register.error'));
        } finally {
            setLoading(false);
        }
    };

    // OTP ekranından forma dön (numarayı düzelt)
    const handleBackToForm = () => {
        setStep('form');
        setOtpCode('');
        setOtpExpiresAt(null);
        setSecondsLeft(0);
    };

    const sectorOptions = [
        { value: 'Kuaför', label: t('auth.register.sectors.hairSalon') },
        { value: 'Güzellik Salonu', label: t('auth.register.sectors.beautySalon') },
        { value: 'Masaj / SPA', label: t('auth.register.sectors.massageSpa') },
        { value: 'Diyetisyen', label: t('auth.register.sectors.dietitian') },
        { value: 'Psikolog / Danışmanlık', label: t('auth.register.sectors.psychologist') },
        { value: 'Diş Klinikleri', label: t('auth.register.sectors.dentalClinic') },
        { value: 'Diğer/Boş', label: t('auth.register.sectors.other') },
    ];

    return (
        <div className="bg-white animate-slide-down register-page-container">
            {/* Toast'u safe-area kadar aşağı it — notch/dynamic island'a girip
                yarım görünmesin. `--offset` sonner'ın içerideki spacing
                CSS değişkenidir; mobilde `env(safe-area-inset-top)`
                değerini, desktop'ta minimum 16px nefes payını uygular. */}
            <Toaster
              position="top-center"
              richColors
              style={{ '--offset': 'max(20px, calc(env(safe-area-inset-top, 0px) + 12px))' }}
            />
            <div className="flex justify-center items-start md:items-center min-h-screen md:min-h-screen p-4">
            <div className="w-full max-w-md">
                {/* Logo & Title */}
                <div className="text-center mb-8">
                    <h1 className="text-4xl font-bold text-gray-900 mb-2">{t('brand.name')}</h1>
                    <p className="text-gray-600">{t('brand.tagline')}</p>
                </div>

                <Card className="shadow-2xl border-0">
                    <CardHeader className="space-y-1 pb-6">
                        <div className="flex justify-end mb-2">
                            <Button 
                                variant="ghost" 
                                size="sm"
                                onClick={() => i18n.changeLanguage(i18n.language === 'tr' ? 'en' : 'tr')}
                                className="text-gray-500 hover:text-gray-700"
                            >
                                <Globe className="w-4 h-4 mr-1" />
                                {i18n.language === 'tr' ? '🇬🇧 EN' : '🇹🇷 TR'}
                            </Button>
                        </div>
                        <CardTitle className="text-2xl md:text-3xl font-bold text-center text-gray-900">
                            {t('auth.register.title')}
                        </CardTitle>
                        <CardDescription className="text-center text-base">
                            {t('auth.register.subtitle')}
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        {step === 'otp' && (
                            <div className="space-y-6">
                                <div className="flex flex-col items-center text-center space-y-3">
                                    <div className="w-16 h-16 rounded-full bg-green-50 flex items-center justify-center">
                                        <MessageCircle className="w-8 h-8 text-green-600" />
                                    </div>
                                    <h3 className="text-lg font-semibold text-gray-900">
                                        {t('auth.register.otpTitle', 'Doğrulama kodu gönderildi')}
                                    </h3>
                                    <p className="text-sm text-gray-600">
                                        {t('auth.register.otpDescription', 'WhatsApp\'a gönderilen 6 haneli kodu girin.')}
                                        {phoneMasked && (
                                            <span className="block mt-1 font-medium text-gray-900">{phoneMasked}</span>
                                        )}
                                    </p>
                                </div>
                                <form onSubmit={handleVerify} className="space-y-5">
                                    <div className="space-y-2">
                                        <Label htmlFor="otp_code" className="text-sm font-semibold text-gray-700">
                                            {t('auth.register.otpLabel', 'Doğrulama Kodu')}
                                        </Label>
                                        <Input
                                            ref={otpInputRef}
                                            id="otp_code"
                                            name="otp_code"
                                            type="text"
                                            inputMode="numeric"
                                            autoComplete="one-time-code"
                                            value={otpCode}
                                            onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                            placeholder="123456"
                                            className="text-center tracking-[0.5em] font-mono text-2xl h-14 border-2 focus:border-gray-900"
                                            maxLength={6}
                                            required
                                        />
                                        {secondsLeft > 0 && (
                                            <p className="text-xs text-gray-500 text-center">
                                                {t('auth.register.otpExpires', 'Kodun geçerlilik süresi:')} {formatSecs(secondsLeft)}
                                            </p>
                                        )}
                                        {secondsLeft === 0 && otpExpiresAt && (
                                            <p className="text-xs text-red-600 text-center">
                                                {t('auth.register.otpExpired', 'Kod süresi doldu. Lütfen yeni kod isteyin.')}
                                            </p>
                                        )}
                                    </div>
                                    <Button
                                        type="submit"
                                        className="w-full h-12 bg-gray-900 hover:bg-gray-800 text-white font-semibold rounded-full shadow-lg transition-all duration-200"
                                        disabled={loading || otpCode.length !== 6}
                                    >
                                        {loading ? t('auth.register.verifying', 'Doğrulanıyor...') : t('auth.register.verifyButton', 'Doğrula ve Hesabı Oluştur')}
                                    </Button>
                                </form>
                                <div className="flex flex-col gap-1 pt-2 border-t border-gray-100">
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        onClick={handleResend}
                                        disabled={resendCooldown > 0 || loading}
                                        className="text-sm text-gray-600 hover:text-gray-900"
                                    >
                                        {resendCooldown > 0
                                            ? t('auth.register.resendIn', 'Yeniden gönder ({{s}}sn)', { s: resendCooldown })
                                            : t('auth.register.resend', 'Kodu yeniden gönder')}
                                    </Button>
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        onClick={handleBackToForm}
                                        disabled={loading}
                                        className="text-sm text-gray-600 hover:text-gray-900"
                                    >
                                        <ArrowLeft className="w-4 h-4 mr-1" />
                                        {t('auth.register.changePhone', 'Numarayı düzelt')}
                                    </Button>
                                </div>
                            </div>
                        )}
                        {step === 'form' && (
                        <form onSubmit={handleRegister} onFocus={handleFormFocus} className="space-y-5">
                            <div className="space-y-2">
                                <Label htmlFor="organization_name" className="text-sm font-semibold text-gray-700">
                                    {t('auth.register.businessName')}
                                </Label>
                                <div className="relative">
                                    <Building2 className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                                    <Input
                                        id="organization_name"
                                        name="organization_name"
                                        type="text"
                                        value={formData.organization_name}
                                        onChange={handleChange}
                                        placeholder={t('auth.register.businessNamePlaceholder')}
                                        className="pl-10 h-12 border-2 focus:border-gray-900"
                                        required
                                    />
                                </div>
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="sector" className="text-sm font-semibold text-gray-700">
                                    {t('auth.register.sector')}
                                </Label>
                                <Select
                                    value={formData.sector}
                                    onValueChange={(value) => setFormData({ ...formData, sector: value })}
                                >
                                    <SelectTrigger className="h-12 border-2 focus:border-gray-900">
                                        <SelectValue placeholder={t('auth.register.sectorPlaceholder')} />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {sectorOptions.map((option) => (
                                            <SelectItem key={option.value} value={option.value}>
                                                {option.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                {formData.sector === "Diğer/Boş" && (
                                    <p className="text-xs text-amber-600 mt-1">
                                        {t('auth.register.sectorWarning')}
                                    </p>
                                )}
                                {formData.sector && formData.sector !== "Diğer/Boş" && (
                                    <p className="text-xs text-green-600 mt-1">
                                        {t('auth.register.sectorSuccess')}
                                    </p>
                                )}
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="full_name" className="text-sm font-semibold text-gray-700">
                                    {t('auth.register.fullName')}
                                </Label>
                                <div className="relative">
                                    <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                                    <Input
                                        id="full_name"
                                        name="full_name"
                                        type="text"
                                        value={formData.full_name}
                                        onChange={handleChange}
                                        placeholder={t('auth.register.fullNamePlaceholder')}
                                        className="pl-10 h-12 border-2 focus:border-gray-900"
                                        required
                                    />
                                </div>
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="username" className="text-sm font-semibold text-gray-700">
                                    {t('auth.register.email')}
                                </Label>
                                <div className="relative">
                                    <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                                    <Input
                                        id="username"
                                        name="username"
                                        type="email"
                                        value={formData.username}
                                        onChange={handleChange}
                                        placeholder={t('auth.register.email')}
                                        className="pl-10 h-12 border-2 focus:border-gray-900"
                                        required
                                    />
                                </div>
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="support_phone" className="text-sm font-semibold text-gray-700">
                                    {t('auth.register.phone')}
                                </Label>
                                <div className="relative">
                                    <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                                    <Input
                                        id="support_phone"
                                        name="support_phone"
                                        type="tel"
                                        value={formData.support_phone}
                                        onChange={handlePhoneChange}
                                        placeholder={i18n.language === 'en' ? '+44XXXXXXXXXX' : '+905XXXXXXXXX'}
                                        className="pl-10 h-12 border-2 focus:border-gray-900"
                                        required
                                        minLength={13}
                                        maxLength={13}
                                    />
                                </div>
                            </div>

                            <div className="space-y-2">
                                <Label htmlFor="password" className="text-sm font-semibold text-gray-700">
                                    {t('auth.register.password')}
                                </Label>
                                <div className="relative">
                                    <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                                    <Input
                                        id="password"
                                        name="password"
                                        type="password"
                                        value={formData.password}
                                        onChange={handleChange}
                                        placeholder="••••••••"
                                        className="pl-10 h-12 border-2 focus:border-gray-900"
                                        required
                                    />
                                </div>
                            </div>

                            <Button 
                                type="submit" 
                                className="w-full h-12 bg-gray-900 hover:bg-gray-800 text-white font-semibold rounded-full shadow-lg transition-all duration-200" 
                                disabled={loading}
                            >
                                {loading ? t('auth.register.registering') : t('auth.register.registerButton')}
                            </Button>
                            
                            <p className="text-xs md:text-sm text-gray-600 text-center mt-3 leading-relaxed">
                                {t('auth.register.guarantee')}
                            </p>
                        </form>
                        )}

                        {step === 'form' && (
                        <div className="mt-6 pt-6 border-t border-gray-200 text-center">
                            <p className="text-sm text-gray-600 mb-3">{t('auth.register.hasAccount')}</p>
                            <Button
                                variant="outline"
                                onClick={() => navigate('/login')}
                                className="w-full h-12 border-2 border-gray-900 text-gray-900 hover:bg-gray-900 hover:text-white font-semibold rounded-full transition-all duration-200"
                            >
                                {t('auth.register.loginLink')}
                                <ArrowRight className="w-4 h-4 ml-2" />
                            </Button>
                        </div>
                        )}
                    </CardContent>
                </Card>

                {!isAppMode && (
                    <div className="text-center mt-4 md:mt-6">
                        <Button
                            variant="outline"
                            onClick={() => navigate('/')}
                            className="text-gray-900 hover:text-white hover:bg-gray-900 border-2 border-gray-900 px-6 py-3 text-base md:text-lg font-semibold rounded-lg transition-all duration-200 shadow-md"
                        >
                            {t('common.backToHome')}
                        </Button>
                    </div>
                )}
                </div>
            </div>
        </div>
    );
};

export default RegisterPage;
