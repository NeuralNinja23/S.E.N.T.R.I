import time
import uuid
import asyncio
import logging
from typing import AsyncGenerator, Tuple, Union, List, Dict, Any

from app.conversation.interfaces import ISpeechToSpeechModel
from app.conversation.contracts import ConversationTurn, AudioChunk
from app.conversation.event_bus import (
    EventBus, SpeechStarted, SpeechFinished, TranscriptReady,
    ReasoningStarted, TokenGenerated, ChunkReady, AudioStarted,
    AudioChunkEvent, AudioFinished, Error
)
from app.conversation.prompt_builder import PromptBuilder
from app.conversation.system_prompt import SystemPromptProvider
from app.conversation.memory_provider import MemoryProvider
from app.conversation.streaming_pipeline.providers.registry import ProviderRegistry
from app.conversation.streaming_pipeline.chunker import ResponseChunker

from app.config import (
    ASR_PROVIDER, REASONING_PROVIDER, REASONING_MODEL,
    TTS_PROVIDER, TTS_SPEAKER_VOICE
)

logger = logging.getLogger("streaming_speech_pipeline")

class StreamingSpeechPipeline(ISpeechToSpeechModel):
    """
    Orchestrates the in-memory decoupled speech pipeline (ASR -> LLM reasoning -> Chunker -> TTS)
    using strongly typed data contracts and publishing lifecycle events.
    """
    def __init__(self):
        # Instantiate provider drivers dynamically
        self.asr = ProviderRegistry.get_asr(ASR_PROVIDER)
        self.reasoning = ProviderRegistry.get_reasoning(REASONING_PROVIDER, model_name=REASONING_MODEL)
        self.tts = ProviderRegistry.get_tts(TTS_PROVIDER, voice_name=TTS_SPEAKER_VOICE)
        self.chunker = ResponseChunker()
        self.event_bus = EventBus()

        # Context components
        self.prompt_builder = PromptBuilder()
        self.system_prompt_provider = SystemPromptProvider()
        self.memory_provider = MemoryProvider()

        self._register_event_loggers()

    def _register_event_loggers(self):
        self.event_bus.subscribe(SpeechStarted, lambda e: logger.info(f"[{e.turn_id}] SpeechStarted"))
        self.event_bus.subscribe(SpeechFinished, lambda e: logger.info(f"[{e.turn_id}] SpeechFinished"))
        self.event_bus.subscribe(TranscriptReady, lambda e: logger.info(f"[{e.turn_id}] TranscriptReady: '{e.text}'"))
        self.event_bus.subscribe(ReasoningStarted, lambda e: logger.info(f"[{e.turn_id}] ReasoningStarted"))
        self.event_bus.subscribe(TokenGenerated, lambda e: logger.debug(f"[{e.turn_id}] TokenGenerated: '{e.token}'"))
        self.event_bus.subscribe(ChunkReady, lambda e: logger.info(f"[{e.turn_id}] ChunkReady: '{e.text}'"))
        self.event_bus.subscribe(AudioStarted, lambda e: logger.info(f"[{e.turn_id}] AudioStarted"))
        self.event_bus.subscribe(AudioFinished, lambda e: logger.info(f"[{e.turn_id}] AudioFinished"))
        self.event_bus.subscribe(Error, lambda e: logger.error(f"[{e.turn_id}] Error: {e.message}"))

    async def process_audio_stream_with_text(
        self,
        audio_generator: AsyncGenerator[bytes, None],
        history: List[Dict[str, Any]] = None
    ) -> AsyncGenerator[Tuple[str, Union[bytes, str]], None]:
        """
        Processes real-time speech bytes. Translates, reasons, chunks, and streams
        audio responses and text tokens.
        """
        turn_id = f"turn_{uuid.uuid4().hex[:8]}"
        turn = ConversationTurn(id=turn_id, timestamp=time.time())
        turn.metrics.end_to_end.start()

        from time import perf_counter
        t_start = perf_counter()

        # 1. Capture raw PCM16 bytes in-memory (no disk IO)
        pcm_bytes = bytearray()
        async for chunk in audio_generator:
            pcm_bytes.extend(chunk)

        if not pcm_bytes:
            logger.warning(f"[{turn_id}] Empty audio input stream.")
            return

        self.event_bus.publish(SpeechStarted(turn_id=turn_id))
        self.event_bus.publish(SpeechFinished(turn_id=turn_id))

        # 2. ASR
        t0 = perf_counter()
        turn.metrics.asr.start()
        transcript = await self.asr.transcribe(bytes(pcm_bytes))
        turn.metrics.asr.stop()
        t_asr = (perf_counter() - t0) * 1000

        turn.transcript = transcript
        self.event_bus.publish(TranscriptReady(turn_id=turn_id, text=transcript))

        if not transcript or not transcript.strip():
            logger.warning(f"[{turn_id}] No spoken words detected. ASR took {t_asr:.0f}ms")
            turn.metrics.end_to_end.stop()
            return

        yield "user_transcript", transcript

        # 3. Memory retrieval
        t0 = perf_counter()
        system_prompt = self.system_prompt_provider.build()
        memory_context = await asyncio.to_thread(self.memory_provider.retrieve)
        t_memory = (perf_counter() - t0) * 1000

        # 4. Prompt builder
        t0 = perf_counter()
        turn.memory_context = memory_context
        reasoning_request = self.prompt_builder.build(
            system_prompt=system_prompt,
            memory=memory_context,
            history=history or [],
            transcript=transcript
        )
        turn.reasoning_request = reasoning_request
        t_prompt = (perf_counter() - t0) * 1000

        self.event_bus.publish(ReasoningStarted(turn_id=turn_id))
        turn.metrics.llm.start()

        first_token = True
        first_audio = True
        accumulated_text = []
        t_ttft = 0.0
        t_tts_total = 0.0
        t_ollama_start = perf_counter()

        try:
            # 5. Stream LLM tokens → Chunker → TTS
            async for token in self.reasoning.stream(reasoning_request):
                self.event_bus.publish(TokenGenerated(turn_id=turn_id, token=token))
                yield "text", token
                accumulated_text.append(token)

                if first_token:
                    t_ttft = (perf_counter() - t_ollama_start) * 1000
                    turn.metrics.ttft = time.time() - turn.metrics.end_to_end.start_time
                    first_token = False

                async for chunk in self.chunker.feed(token):
                    self.event_bus.publish(ChunkReady(turn_id=turn_id, text=chunk))

                    t0 = perf_counter()
                    turn.metrics.tts.start()
                    async for audio_bytes in self.tts.synthesize(chunk):
                        if first_audio:
                            turn.metrics.ttfa = time.time() - turn.metrics.end_to_end.start_time
                            self.event_bus.publish(AudioStarted(turn_id=turn_id))
                            first_audio = False
                        self.event_bus.publish(AudioChunkEvent(turn_id=turn_id, pcm_bytes=audio_bytes))
                        yield "audio", audio_bytes
                        turn.audio_chunks.append(AudioChunk(pcm_bytes=audio_bytes))
                    turn.metrics.tts.stop()
                    t_tts_total += (perf_counter() - t0) * 1000

            # 6. Flush remaining chunker buffer
            remaining_chunk = self.chunker.flush()
            if remaining_chunk:
                self.event_bus.publish(ChunkReady(turn_id=turn_id, text=remaining_chunk))
                t0 = perf_counter()
                turn.metrics.tts.start()
                async for audio_bytes in self.tts.synthesize(remaining_chunk):
                    if first_audio:
                        turn.metrics.ttfa = time.time() - turn.metrics.end_to_end.start_time
                        self.event_bus.publish(AudioStarted(turn_id=turn_id))
                        first_audio = False
                    self.event_bus.publish(AudioChunkEvent(turn_id=turn_id, pcm_bytes=audio_bytes))
                    yield "audio", audio_bytes
                    turn.audio_chunks.append(AudioChunk(pcm_bytes=audio_bytes))
                turn.metrics.tts.stop()
                t_tts_total += (perf_counter() - t0) * 1000

        except Exception as err:
            self.event_bus.publish(Error(turn_id=turn_id, message=str(err)))
            raise err
        finally:
            turn.metrics.llm.stop()
            turn.metrics.end_to_end.stop()
            self.event_bus.publish(AudioFinished(turn_id=turn_id))
            turn.reasoning_response = "".join(accumulated_text)

            t_total = (perf_counter() - t_start) * 1000
            t_ollama_total = t_total - t_asr - t_memory - t_prompt - t_tts_total

            logger.info(
                f"\n[PIPELINE TIMING] {turn_id}\n"
                f"  ASR              {t_asr:>8.0f} ms\n"
                f"  Memory           {t_memory:>8.0f} ms\n"
                f"  Prompt           {t_prompt:>8.0f} ms\n"
                f"  Ollama (TTFT)    {t_ttft:>8.0f} ms\n"
                f"  Ollama (total)   {t_ollama_total:>8.0f} ms\n"
                f"  TTS (cumulative) {t_tts_total:>8.0f} ms\n"
                f"  {'─'*30}\n"
                f"  Total            {t_total:>8.0f} ms"
            )

    async def process_audio_stream(
        self,
        audio_generator: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[bytes, None]:
        """
        Complies with standard ISpeechToSpeechModel interface yielding audio bytes only.
        """
        async for event_type, content in self.process_audio_stream_with_text(audio_generator):
            if event_type == "audio":
                yield content
