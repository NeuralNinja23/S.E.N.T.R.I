import React, { useState, useEffect, useRef } from "react";
import SectionTitle from "../ui/SectionTitle";
import { COLORS, SHADOWS } from "../constants/colors";
import { Send, Cpu, User, Mic, MicOff, Square } from "lucide-react";
import { voiceService } from "../../services/voice.service";

interface ChatBoxProps {
    logs?: string[];
    onSendCommand?: (text: string) => void;
    isRecording?: boolean;
    onToggleRecording?: () => void;
    speakingState?: string;
}

interface ChatMessage {
    time: string;
    sender: "user" | "sentri";
    text: string;
}

export default function ChatBox({ 
    logs = [], 
    onSendCommand,
    isRecording = false,
    onToggleRecording,
    speakingState = "INACTIVE"
}: ChatBoxProps) {
    const [inputValue, setInputValue] = useState("");
    const [currentTime, setCurrentTime] = useState<Date | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Running clock effect
    useEffect(() => {
        setCurrentTime(new Date());
        const timer = setInterval(() => setCurrentTime(new Date()), 1000);
        return () => clearInterval(timer);
    }, []);

    const formatTime = (date: Date | null) => {
        if (!date) return "--:--:--";
        return date.toLocaleTimeString("en-US", {
            hour12: false,
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
        });
    };

    // Parse raw logs from voiceStore to extract user and sentri dialogue
    const messages: ChatMessage[] = logs
        .map((logStr) => {
            const match = logStr.match(/^\[(\d{2}:\d{2}:\d{2})\]\s*(.*)$/s);
            const timeVal = match ? match[1] : "00:00:00";
            const content = match ? match[2] : logStr;

            if (content.startsWith("USER:")) {
                return {
                    time: timeVal,
                    sender: "user" as const,
                    text: content.replace("USER:", "").trim(),
                };
            }
            if (content.startsWith("USER COMMAND:")) {
                return {
                    time: timeVal,
                    sender: "user" as const,
                    text: content.replace("USER COMMAND:", "").trim(),
                };
            }
            if (content.startsWith("SENTRI:")) {
                return {
                    time: timeVal,
                    sender: "sentri" as const,
                    text: content.replace("SENTRI:", "").trim(),
                };
            }
            return null;
        })
        .filter((msg): msg is ChatMessage => msg !== null);

    // Auto-scroll to bottom of conversation
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages.length]);

    const handleSend = () => {
        if (inputValue.trim() && onSendCommand) {
            onSendCommand(inputValue.trim());
            setInputValue("");
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Enter") {
            handleSend();
        }
    };

    return (
        <div className="flex flex-col h-full w-full">
            {/* Digital Clock Header */}
            <div className="flex flex-col items-end text-right w-full mb-4">
                <span
                    className="text-3xl font-bold tracking-[0.1em] drop-shadow-[0_0_10px_rgba(0,229,255,0.5)]"
                    style={{ color: COLORS.cyanBright }}
                >
                    {formatTime(currentTime)}
                </span>
            </div>

            <div className="flex justify-start items-start">
                <SectionTitle title="SENTRI Dialogue" />
            </div>

            {/* Chat Container */}
            <div className="flex-1 min-h-0 relative overflow-hidden border border-cyan-900/30 bg-black/35 rounded-md shadow-[inset_0_0_20px_rgba(0,229,255,0.03)] mt-2 p-4 flex flex-col justify-between">
                
                {/* Sci-Fi Border Corners */}
                <div className="absolute top-0 left-0 w-2.5 h-2.5 border-t border-l border-cyan-400" />
                <div className="absolute top-0 right-0 w-2.5 h-2.5 border-t border-r border-cyan-400" />
                <div className="absolute bottom-0 left-0 w-2.5 h-2.5 border-b border-l border-cyan-400" />
                <div className="absolute bottom-0 right-0 w-2.5 h-2.5 border-b border-r border-cyan-400" />

                {/* Subtitle / Status indicator */}
                <div className="flex items-center justify-between mb-3 text-[9px] tracking-[0.25em] uppercase select-none">
                    <span style={{ color: COLORS.textSecondary }}>COMMUNICATION NODE</span>
                    <div className="flex items-center gap-1.5">
                        <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(0,229,255,0.8)] animate-pulse" />
                        <span style={{ color: COLORS.cyan }}>ENCRYPTED</span>
                    </div>
                </div>

                {/* Messages Dialogue Stream */}
                <div className="flex-1 overflow-y-auto pr-1 mb-4 flex flex-col gap-3.5 custom-scrollbar min-h-0">
                    {messages.length === 0 ? (
                        <div className="flex-1 flex flex-col items-center justify-center text-center opacity-40 px-6 py-12 select-none">
                            <Cpu size={32} className="text-cyan-500 mb-3 animate-pulse" />
                            <p className="text-[10px] tracking-widest uppercase text-cyan-400">
                                Dialogue initiated. Standby for voice or text interaction...
                            </p>
                        </div>
                    ) : (
                        messages.map((msg, index) => {
                            const isUser = msg.sender === "user";
                            return (
                                <div
                                    key={index}
                                    className={`flex w-full flex-col ${
                                        isUser ? "items-end animate-[slideInRight_0.2s_ease-out]" : "items-start animate-[slideInLeft_0.2s_ease-out]"
                                    }`}
                                >
                                    {/* Sender Meta (Time + Label) */}
                                    <div className="flex items-center gap-2 mb-1 text-[8px] tracking-widest uppercase opacity-60">
                                        {!isUser && <Cpu size={8} className="text-orange-500" />}
                                        <span style={{ color: isUser ? COLORS.cyan : COLORS.orange }}>
                                            {isUser ? "USER" : "SENTRI"}
                                        </span>
                                        <span className="text-slate-500">{msg.time}</span>
                                        {isUser && <User size={8} className="text-cyan-400" />}
                                    </div>

                                    {/* Message Bubble */}
                                    <div
                                        className={`max-w-[85%] rounded px-3.5 py-2.5 text-[11px] tracking-wider leading-relaxed border relative shadow-md ${
                                            isUser
                                                ? "border-cyan-500/35 bg-cyan-950/15 text-cyan-200"
                                                : "border-orange-500/35 bg-orange-950/10 text-slate-100"
                                        }`}
                                        style={{
                                            boxShadow: isUser ? SHADOWS.cyan : SHADOWS.orange,
                                        }}
                                    >
                                        {/* Subtle corner highlighting for bubbles */}
                                        <div
                                            className={`absolute top-0 w-1.5 h-1.5 border-t ${
                                                isUser
                                                    ? "left-0 border-l border-cyan-400"
                                                    : "right-0 border-r border-orange-400"
                                            }`}
                                        />
                                        <div
                                            className={`absolute bottom-0 w-1.5 h-1.5 border-b ${
                                                isUser
                                                    ? "right-0 border-r border-cyan-400"
                                                    : "left-0 border-l border-orange-400"
                                            }`}
                                        />
                                        <p className="whitespace-pre-wrap break-words">{msg.text}</p>
                                    </div>
                                </div>
                            );
                        })
                    )}
                    <div ref={messagesEndRef} />
                </div>

                {/* Bottom Input Area */}
                <div className="relative border border-cyan-900/60 bg-black/40 rounded flex items-center shadow-[inset_0_0_10px_rgba(0,229,255,0.05)] p-1">
                    {/* Sci-Fi Corners */}
                    <div className="absolute top-0 left-0 w-2 h-2 border-t border-l border-cyan-500" />
                    <div className="absolute top-0 right-0 w-2 h-2 border-t border-r border-cyan-500" />
                    <div className="absolute bottom-0 left-0 w-2 h-2 border-b border-l border-cyan-500" />
                    <div className="absolute bottom-0 right-0 w-2 h-2 border-b border-r border-cyan-500" />

                    <input
                        placeholder="Type message to SENTRI..."
                        className="w-full bg-transparent outline-none text-[11px] px-3 py-2.5 tracking-wider text-cyan-200 mr-20"
                        style={{ color: COLORS.cyanBright }}
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={handleKeyDown}
                    />
                    
                    {/* Action Buttons Group */}
                    <div className="absolute right-1 flex items-center gap-1.5">
                        {/* Stop Speaking / Mute Button */}
                        {(speakingState === "SPEAKING" || speakingState === "THINKING") && (
                            <button
                                onClick={() => voiceService.stopSpeaking()}
                                className="p-2 text-red-500 border border-red-500/50 rounded hover:bg-red-950/40 hover:text-red-400 transition-colors"
                                title="Stop SENTRI from Speaking"
                            >
                                <Square size={13} fill="currentColor" />
                            </button>
                        )}

                        {/* Microphone Toggle Button */}
                        <button
                            onClick={onToggleRecording}
                            className={`p-2 rounded transition-colors ${
                                isRecording
                                    ? "text-green-400 border border-green-500 bg-green-950/40 animate-pulse animate-duration-[1.5s]"
                                    : "text-cyan-500 border border-cyan-900/50 hover:bg-cyan-950/20 hover:text-cyan-400"
                            }`}
                            title={isRecording ? "Deactivate Microphone" : "Activate Microphone"}
                        >
                            {isRecording ? <MicOff size={13} /> : <Mic size={13} />}
                        </button>

                        {/* Send Button */}
                        <button
                            onClick={handleSend}
                            className="p-2 text-orange-500 border border-orange-500/50 rounded hover:bg-orange-950/40 hover:text-orange-400 transition-colors"
                            style={{
                                boxShadow: `0 0 6px rgba(255,138,0,0.15)`,
                            }}
                        >
                            <Send size={13} />
                        </button>
                    </div>
                </div>

            </div>
        </div>
    );
}
