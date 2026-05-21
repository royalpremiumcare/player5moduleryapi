import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Sparkles, X, Send, Loader2, Mic, MicOff } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import api from '@/api/api';

// Capacitor native plugins (Android/iOS) — web'de graceful fallback
let CapacitorTTS = null;
let CapacitorSTT = null;
let CapacitorCore = null;
try {
  const ttsModule = require('@capacitor-community/text-to-speech');
  CapacitorTTS = ttsModule.TextToSpeech;
} catch (_) {}
try {
  const sttModule = require('@capacitor-community/speech-recognition');
  CapacitorSTT = sttModule.SpeechRecognition;
} catch (_) {}
try {
  const coreModule = require('@capacitor/core');
  CapacitorCore = coreModule.Capacitor;
} catch (_) {}

const isNative = () => CapacitorCore && CapacitorCore.isNativePlatform();

const speakText = async (text, lang = 'tr-TR') => {
  const clean = text.replace(/[#*_`]/g, '').substring(0, 400);
  if (CapacitorTTS) {
    try {
      await CapacitorTTS.stop();
      await CapacitorTTS.speak({ text: clean, lang, rate: 1.0, pitch: 1.0, volume: 1.0, category: 'ambient' });
      return;
    } catch (_) {}
  }
  // Web fallback
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel();
    window.speechSynthesis.resume();
    const u = new SpeechSynthesisUtterance(clean);
    const voices = window.speechSynthesis.getVoices();
    const voice = voices.find(v => v.lang.startsWith(lang.split('-')[0]));
    if (voice) { u.voice = voice; u.lang = voice.lang; }
    window.speechSynthesis.speak(u);
  }
};

const ChatWidget = ({ user, externalOpen, onExternalClose }) => {
  const { t, i18n } = useTranslation();
  const ttsLang = i18n.language === 'en' ? 'en-GB' : 'tr-TR';
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (externalOpen) setIsOpen(true);
  }, [externalOpen]);

  const handleClose = () => {
    setIsOpen(false);
    if (onExternalClose) onExternalClose();
  };
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const [usageInfo, setUsageInfo] = useState({ current: 0, limit: -1 });
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);

  // AI modal açıkken arka plan (#app-wrapper) kaymasın — scroll kilidi.
  // Panel mimarisinde scroll body'de değil #app-wrapper üzerinde olduğu için
  // Radix/shadcn modal kilidi yetmiyor; touch/wheel dışarı sızınca dashboard kayıyordu.
  useEffect(() => {
    if (!isOpen) return;

    const wrapper = document.getElementById('app-wrapper');
    const savedScrollTop = wrapper?.scrollTop ?? 0;
    const prevOverflow = wrapper?.style.overflow ?? '';

    if (wrapper) {
      wrapper.style.overflow = 'hidden';
    }

    const allowScrollInsideMessages = (target) => {
      const el = messagesContainerRef.current;
      return el && el.contains(target);
    };

    const blockBackgroundTouch = (e) => {
      if (allowScrollInsideMessages(e.target)) return;
      e.preventDefault();
    };

    const blockBackgroundWheel = (e) => {
      if (allowScrollInsideMessages(e.target)) return;
      e.preventDefault();
    };

    document.addEventListener('touchmove', blockBackgroundTouch, { passive: false });
    document.addEventListener('wheel', blockBackgroundWheel, { passive: false });

    return () => {
      document.removeEventListener('touchmove', blockBackgroundTouch);
      document.removeEventListener('wheel', blockBackgroundWheel);
      if (wrapper) {
        wrapper.style.overflow = prevOverflow;
        wrapper.scrollTop = savedScrollTop;
      }
    };
  }, [isOpen]);

  // Voice mode states
  const [voiceMode, setVoiceMode] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef(null);
  const voiceActiveRef = useRef(false); // stale closure'dan bağımsız flag

  const sampleQuestions = useMemo(() => {
    if (i18n.language === 'en') {
      return user?.role === 'admin'
        ? ["What's today's status? 📊", "How many appointments this month?", "How is staff performance?", "Create appointment for tomorrow 📅"]
        : ["How many appointments do I have today?", "How much did I earn this month? 💸", "Show my tomorrow appointments", "How do I use the system?"];
    }
    return user?.role === 'admin'
      ? ["Bugün durum ne? 📊", "Bu ay kaç randevumuz var?", "Personel performansı nasıl?", "Yarın için randevu oluştur 📅"]
      : ["Bugün kaç randevum var?", "Bu ay ne kadar kazandım? 💸", "Yarınki randevularımı göster", "Sistem nasıl kullanılır?"];
  }, [i18n.language, user?.role]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (isOpen && messages.length === 0) {
      // İlk açılışta hoş geldin mesajı
      setMessages([{
        role: 'assistant',
        content: t('chat.welcome', { name: user?.full_name || user?.username })
      }]);
    }
  }, [isOpen, messages.length, user]);

  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = inputMessage.trim();
    setInputMessage('');

    // Kullanıcı mesajını ekle
    const newMessages = [...messages, { role: 'user', content: userMessage }];
    setMessages(newMessages);
    setIsLoading(true);

    try {
      const { data } = await api.post('/ai/chat', {
        message: userMessage,
        history: chatHistory,
        language: i18n.language
      });

      // AI yanıtını ekle
      setMessages([...newMessages, { 
        role: 'assistant', 
        content: (data && data.message) || t('chat.done')
      }]);

      // Chat history'yi güncelle
      if (data && data.history) {
        setChatHistory(data.history);
      }

      // Kullanım bilgisini güncelle
      if (data && data.usage_info) {
        setUsageInfo(data.usage_info);
      }

    } catch (error) {
      console.error('AI chat error:', error);
      
      if (error.response && (error.response.data?.detail || error.response.data?.message)) {
        const serverMsg = error.response.data.detail || error.response.data.message;
        setMessages([...newMessages, { role: 'assistant', content: `❌ ${serverMsg}` }]);
      } else if (error.message) {
        setMessages([...newMessages, { role: 'assistant', content: `❌ ${error.message}` }]);
      } else {
        setMessages([...newMessages, { role: 'assistant', content: t('chat.error') }]);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuestionClick = (question) => {
    setInputMessage(question);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // === VOICE MODE ===
  const toggleVoiceMode = () => {
    if (voiceMode) stopVoiceMode();
    else startVoiceMode();
  };

  // Transkripti AI'ya gönder ve yanıt al
  const handleTranscript = async (transcript) => {
    if (!voiceActiveRef.current || !transcript.trim()) return;
    setIsListening(false);

    const newMessages = [...messages, { role: 'user', content: transcript }];
    setMessages(newMessages);
    setIsLoading(true);
    try {
      const { data } = await api.post('/ai/chat', { message: transcript, history: chatHistory, language: i18n.language });
      const aiText = (data && data.message) || t('chat.done');
      setMessages([...newMessages, { role: 'assistant', content: aiText }]);
      if (data?.history) setChatHistory(data.history);
      if (data?.usage_info) setUsageInfo(data.usage_info);
      speakText(aiText, ttsLang).catch(() => {});
    } catch (error) {
      const errMsg = error.response?.data?.detail || error.message || t('chat.errorOccurred');
      setMessages([...newMessages, { role: 'assistant', content: `❌ ${errMsg}` }]);
    } finally {
      setIsLoading(false);
      // Bir sonraki dinleme turu
      if (voiceActiveRef.current) setTimeout(() => startListeningCycle(), 400);
    }
  };

  // Tek bir dinleme turu başlat (native veya web)
  const startListeningCycle = async () => {
    if (!voiceActiveRef.current) return;

    if (isNative() && CapacitorSTT) {
      // === NATIVE (Android / iOS) ===
      try {
        setIsListening(true);
        // partialResults listener temizle, yeni ekle
        await CapacitorSTT.removeAllListeners();
        await CapacitorSTT.addListener('partialResults', async (data) => {
          if (!voiceActiveRef.current) return;
          const match = data.matches && data.matches[0];
          if (match) {
            await CapacitorSTT.stop().catch(() => {});
            handleTranscript(match);
          }
        });
        await CapacitorSTT.start({ language: ttsLang, maxResults: 1, partialResults: false, popup: false });
      } catch (err) {
        setIsListening(false);
        if (voiceActiveRef.current) setTimeout(startListeningCycle, 800);
      }
    } else {
      // === WEB (Chrome/Edge) ===
      const WebSTT = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!WebSTT) return;
      const rec = new WebSTT();
      rec.lang = ttsLang;
      rec.continuous = false;
      rec.interimResults = false;
      recognitionRef.current = rec;

      rec.onstart = () => setIsListening(true);
      rec.onresult = (e) => {
        const t = e.results[0][0].transcript.trim();
        handleTranscript(t);
      };
      rec.onerror = (e) => {
        setIsListening(false);
        if (e.error === 'aborted' || e.error === 'not-allowed') return;
        if (e.error === 'no-speech' && voiceActiveRef.current) {
          setTimeout(startListeningCycle, 400);
        }
      };
      rec.onend = () => setIsListening(false);
      try { rec.start(); } catch (_) {}
    }
  };

  const startVoiceMode = async () => {
    // Native izin kontrolü
    if (isNative() && CapacitorSTT) {
      try {
        const perm = await CapacitorSTT.requestPermissions();
        if (perm.speechRecognition !== 'granted') {
          setMessages(prev => [...prev, { role: 'assistant', content: t('chat.micDenied') }]);
          return;
        }
      } catch (_) {}
    } else if (!window.SpeechRecognition && !window.webkitSpeechRecognition) {
      setMessages(prev => [...prev, { role: 'assistant', content: t('chat.voiceNotSupported') }]);
      return;
    }

    voiceActiveRef.current = true;
    setVoiceMode(true);
    setMessages(prev => [...prev, { role: 'assistant', content: t('chat.voiceOn') }]);
    startListeningCycle();
  };

  const stopVoiceMode = async () => {
    voiceActiveRef.current = false;
    setVoiceMode(false);
    setIsListening(false);
    if (isNative() && CapacitorSTT) {
      await CapacitorSTT.stop().catch(() => {});
      await CapacitorSTT.removeAllListeners().catch(() => {});
    } else if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (_) {}
      recognitionRef.current = null;
    }
    if (CapacitorTTS) CapacitorTTS.stop().catch(() => {});
    else if (window.speechSynthesis) window.speechSynthesis.cancel();
    setMessages(prev => [...prev, { role: 'assistant', content: t('chat.voiceOff') }]);
  };

  if (!isOpen) return null;

  // Chat penceresi
  return (
    <>
      {/* Scroll shield — arka plana dokunma/kaydırma geçmesin (görünmez) */}
      <div
        className="fixed inset-0 z-[1099] touch-none"
        aria-hidden="true"
        onClick={handleClose}
      />

      <div
        className="fixed right-4 bottom-[calc(env(safe-area-inset-bottom,0px)+72px)] md:bottom-24 md:left-1/2 md:-translate-x-1/2 md:right-auto z-[1100] w-[22rem] max-w-[calc(100vw-2rem)] h-[520px] md:w-[740px] md:h-[460px] bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden border border-gray-200"
        onClick={(e) => e.stopPropagation()}
      >
      {/* Header */}
      <div className="bg-white/80 backdrop-blur-xl border-b border-gray-100 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-gray-900 to-gray-700 flex items-center justify-center shadow-sm shrink-0">
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-gray-900">{t('chat.title')}</h3>
              <p className="text-[11px] text-gray-400">
                {voiceMode ? t('chat.voiceModeActive') : t('chat.subtitle')}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {/* Sesli Mod Toggle */}
            <button
              onClick={toggleVoiceMode}
              className={`p-2 rounded-xl transition-all ${
                voiceMode
                  ? 'bg-red-50 text-red-600 hover:bg-red-100'
                  : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
              }`}
              title={voiceMode ? t('chat.turnOffVoice') : t('chat.turnOnVoice')}
            >
              {voiceMode ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
            </button>
            <button
              onClick={handleClose}
              className="p-2 rounded-xl bg-gray-100 text-gray-500 hover:bg-gray-200 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Quota Gösterimi */}
        {usageInfo.limit === -1 ? (
          <div className="mt-2 text-xs bg-amber-50 text-amber-700 border border-amber-100 px-2.5 py-1 rounded-lg flex items-center gap-1.5">
            <Sparkles className="w-3 h-3" />
            <span>{t('chat.unlimitedAccess')}</span>
          </div>
        ) : usageInfo.current >= usageInfo.limit * 0.9 ? (
          <div className="mt-2 text-xs bg-orange-50 text-orange-700 border border-orange-100 px-2.5 py-1 rounded-lg">
            <span>{t('chat.remaining', { current: usageInfo.current, limit: usageInfo.limit })}</span>
          </div>
        ) : null}
      </div>

      {/* Messages */}
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto overscroll-contain p-4 space-y-4 bg-gray-50"
      >
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2 ${
                msg.role === 'user'
                  ? 'bg-gradient-to-r from-purple-600 to-blue-600 text-white'
                  : 'bg-white text-gray-800 shadow-sm border border-gray-200'
              }`}
            >
              <div className="whitespace-pre-wrap break-words text-sm">
                {msg.content}
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-white rounded-2xl px-4 py-3 shadow-sm border border-gray-200">
              <Loader2 className="w-5 h-5 animate-spin text-purple-600" />
            </div>
          </div>
        )}

        {isListening && (
          <div className="flex flex-col items-center space-y-2">
            <div className="bg-red-100 text-red-600 text-xs px-3 py-1 rounded-full animate-pulse">
              {t('chat.listening')}
            </div>
          </div>
        )}

        {/* Örnek Sorular */}
        {messages.length <= 1 && !isLoading && !voiceMode && (
          <div className="space-y-2">
            <p className="text-xs text-gray-500 text-center">{t('chat.sampleQuestions')}</p>
            {sampleQuestions.map((q, idx) => (
              <button
                key={idx}
                onClick={() => handleQuestionClick(q)}
                className="w-full text-left text-sm bg-white hover:bg-purple-50 text-gray-700 rounded-xl px-4 py-2 border border-gray-200 hover:border-purple-300 transition-all"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input - Sadece voice mode kapalıyken */}
      {!voiceMode && (
        <div className="p-4 bg-white border-t border-gray-200">
        {usageInfo.limit !== -1 && usageInfo.current >= usageInfo.limit ? (
          // Limit doldu - Upgrade butonu göster
          <div className="text-center">
            <button
              onClick={() => window.location.href = '/subscribe'}
              className="w-full bg-gradient-to-r from-orange-500 to-red-600 text-white rounded-xl px-4 py-3 hover:shadow-lg transition-all font-semibold"
            >
              {t('chat.upgradeButton')}
            </button>
            <p className="text-xs text-gray-500 mt-2">
              {t('chat.upgradeDesc')}
            </p>
          </div>
        ) : (
          <>
            <div className="flex space-x-2">
              <input
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={t('chat.placeholder')}
                disabled={isLoading}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
              />
              <button
                onClick={sendMessage}
                disabled={!inputMessage.trim() || isLoading}
                className="bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-xl px-4 py-2 hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
            <p className="text-xs text-gray-400 mt-2 text-center">
              {t('chat.disclaimer')}
            </p>
          </>
        )}
        </div>
      )}
      </div>
    </>
  );
};

export default ChatWidget;