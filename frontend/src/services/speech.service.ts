class SpeechService {
  private recognition: any = null;
  private isActivating = false;

  start(
    onWakeWord: () => void,
    onGovernanceCommand: (cmd: string) => void,
    onUserSpeech: (transcript: string) => void,
    isRecordingRef: { current: boolean },
    onListeningStateTrigger: () => void
  ) {
    if (typeof window === "undefined") return;
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn("Speech recognition is not supported in this browser.");
      return;
    }

    if (this.recognition) {
      try {
        this.recognition.stop();
      } catch (e) {}
    }

    const rec = new SpeechRecognition();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = "en-US";

    rec.onresult = (event: any) => {
      let transcript = "";
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        transcript += event.results[i][0].transcript;
      }

      const isFinal = event.results[event.results.length - 1].isFinal;
      const lower = transcript.toLowerCase();

      // Intercept governance commands immediately for barge-in / interruption
      let govCmd: string | null = null;
      const cleanLower = lower.trim().replace(/[.,\/#!$%\^&\*;:{}=\-_`~()]/g,"");
      
      // Short, natural barge-in commands
      const stopPhrases = [
        "stop speaking", "stop", "shut up", "be quiet", "silence", "enough",
        "hold on", "wait"
      ];
      
      if (stopPhrases.includes(cleanLower) || stopPhrases.some(p => cleanLower.endsWith(" " + p))) {
        govCmd = "stop_speaking";
      } else if (lower.includes("pause all tasks")) {
        govCmd = "pause";
      } else if (lower.includes("resume all tasks")) {
        govCmd = "resume";
      } else if (lower.includes("stop all tasks")) {
        govCmd = "stop";
      } else if (
        lower.includes("standby mode") || 
        lower.includes("stand by mode") || 
        lower.includes("stand-by mode") || 
        lower.includes("standy mode") || 
        lower.includes("enter standby") ||
        lower.includes("enter stand by")
      ) {
        govCmd = "enter_standby";
      } else if (
        lower.includes("wake up") || 
        lower.includes("exit standby") || 
        lower.includes("exit stand by") ||
        lower.includes("wake sentri") || 
        lower.includes("wake sentry") ||
        lower.includes("wake centri") ||
        lower.includes("wake centry")
      ) {
        govCmd = "exit_standby";
      }

      if (govCmd) {
        console.log(`[SpeechService] Intercepted governance command: ${govCmd}`);
        onGovernanceCommand(govCmd);
        return;
      }

      // NOTE: We intentionally do NOT auto-stop recording here.
      // Web Speech API fires isFinal aggressively, often mid-sentence.
      // Turn completion is handled exclusively by the user releasing the button
      // (manual push-to-talk), which calls stopRecording() → turn_complete.
      if (isRecordingRef.current) {
        return;
      }

      if (this.isActivating) return;

      // Check wake words including all ASR phonetic variations
      if (
        lower.includes("sentri") ||
        lower.includes("sentry") ||
        lower.includes("centri") ||
        lower.includes("centry") ||
        lower.includes("sentinal") ||
        lower.includes("centinal") ||
        lower.includes("daddy's home") ||
        lower.includes("daddies home") ||
        lower.includes("daddy is home")
      ) {
        console.log("WAKE WORD DETECTED!");
        this.isActivating = true;
        rec.stop();
        onWakeWord();
        setTimeout(() => {
          this.isActivating = false;
        }, 1200);
      }
    };

    rec.onend = () => {
      if (!this.isActivating && !isRecordingRef.current) {
        try {
          rec.start();
          onListeningStateTrigger();
        } catch (e) {}
      }
    };

    try {
      rec.start();
      onListeningStateTrigger();
    } catch (e) {}

    this.recognition = rec;
  }

  stop() {
    if (this.recognition) {
      try {
        this.recognition.stop();
      } catch (e) {}
      this.recognition = null;
    }
  }
}

export const speechService = new SpeechService();
