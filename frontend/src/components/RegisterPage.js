import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Building2, User, Mail, Lock, ArrowRight, Phone, Globe } from 'lucide-react';
import { toast, Toaster } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardHeader, CardContent, CardTitle, CardDescription } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const RegisterPage = () => { 
    const navigate = useNavigate();
    const { register } = useAuth(); 
    const { t, i18n } = useTranslation();

    // Sayfa yüklendiğinde en üste scroll et ve iOS Chrome scroll sorununu önle
    useEffect(() => {
        window.scrollTo(0, 0);
        
        // iOS Chrome'a özel scroll düzeltmesi
        const isIOSChrome = /CriOS/i.test(navigator.userAgent);
        
        if (isIOSChrome) {
            let maxScroll = 0;
            let isAtBottom = false;
            let lastScrollTop = 0;
            
            const updateMaxScroll = () => {
                const scrollHeight = document.documentElement.scrollHeight;
                const clientHeight = document.documentElement.clientHeight;
                maxScroll = Math.max(maxScroll, scrollHeight - clientHeight);
            };
            
            const handleScroll = () => {
                const currentScrollTop = window.pageYOffset || document.documentElement.scrollTop;
                const scrollHeight = document.documentElement.scrollHeight;
                const clientHeight = document.documentElement.clientHeight;
                const currentMaxScroll = scrollHeight - clientHeight;
                
                updateMaxScroll();
                
                const nearBottom = currentScrollTop + clientHeight >= scrollHeight - 1;
                
                if (nearBottom) {
                    isAtBottom = true;
                    if (currentScrollTop > currentMaxScroll) {
                        window.scrollTo({ top: currentMaxScroll, behavior: 'auto' });
                    }
                    if (currentScrollTop > lastScrollTop && currentScrollTop >= currentMaxScroll - 0.5) {
                        window.scrollTo({ top: currentMaxScroll, behavior: 'auto' });
                    }
                } else {
                    isAtBottom = false;
                }
                
                lastScrollTop = currentScrollTop;
            };
            
            setTimeout(updateMaxScroll, 100);
            setTimeout(updateMaxScroll, 500);
            setTimeout(updateMaxScroll, 1000);
            
            window.addEventListener('scroll', handleScroll, { passive: true });
            window.addEventListener('resize', updateMaxScroll, { passive: true });
            
            let touchStartY = 0;
            const handleTouchStart = (e) => { touchStartY = e.touches[0].clientY; };
            
            const handleTouchMove = (e) => {
                if (isAtBottom) {
                    const touchY = e.touches[0].clientY;
                    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                    const scrollHeight = document.documentElement.scrollHeight;
                    const clientHeight = document.documentElement.clientHeight;
                    
                    if (scrollTop + clientHeight >= scrollHeight - 1 && touchY < touchStartY) {
                        e.preventDefault();
                        window.scrollTo({ top: scrollHeight - clientHeight, behavior: 'auto' });
                    }
                }
            };
            
            document.addEventListener('touchstart', handleTouchStart, { passive: true });
            document.addEventListener('touchmove', handleTouchMove, { passive: false });
            
            return () => {
                window.removeEventListener('scroll', handleScroll);
                window.removeEventListener('resize', updateMaxScroll);
                document.removeEventListener('touchstart', handleTouchStart);
                document.removeEventListener('touchmove', handleTouchMove);
            };
        }
    }, []); 

    const [formData, setFormData] = useState({
        username: '',
        password: '',
        full_name: '',
        organization_name: '',
        support_phone: '+90',
        sector: ''
    });
    const [loading, setLoading] = useState(false);
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
        if (!value.startsWith('+90')) {
            value = '+90' + value.replace(/^\+?90?/, '');
        }
        value = value.replace(/[^0-9+]/g, '');
        if (value.length > 13) {
            value = value.substring(0, 13);
        }
        setFormData({ ...formData, support_phone: value });
    };

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

            if (result.success) {
                toast.success(t('auth.register.success'));
                navigate('/login'); 
            } else {
                toast.error(result.error || t('auth.register.error'));
            }
        } catch (error) {
            toast.error(t('auth.register.error'));
        } finally {
            setLoading(false);
        }
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
            <Toaster position="top-center" richColors />
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
                        <form onSubmit={handleRegister} className="space-y-5">
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
                                        placeholder="+905XXXXXXXXX"
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
