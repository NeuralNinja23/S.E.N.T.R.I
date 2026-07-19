import time
import uuid
import asyncio
import logging
from typing import AsyncGenerator, Tuple, Union, List, Dict, Any

from app.conversation.interfaces import ISpeechToSpeechModel
from app.conversation.contracts import (
    ConversationTurn, AudioChunk, TurnContext, TurnChannels, ConversationClock
)
from app.conversation.event_bus import (
    EventBus, SpeechStarted, SpeechFinished, TranscriptReady,
    ReasoningStarted, TokenGenerated, ChunkReady, AudioStarted,
    AudioChunkEvent, AudioFinished, Error, Interrupted, Cancelled
)
from app.conversation.prompt_builder import PromptBuilder
from app.conversation.system_prompt import SystemPromptProvider
from app.conversation.memory_provider import MemoryProvider
from app.conversation.streaming_pipeline.providers.registry import ProviderRegistry
from app.conversation.streaming_pipeline.chunker import SpeechPlanner

from app.config import (
    ASR_PROVIDER, REASONING_PROVIDER, REASONING_MODEL,
    TTS_PROVIDER, TTS_SPEAKER_VOICE
)

logger = logging.getLogger("conversation_runtime")

class RuntimeSupervisor:
    """
    Manages the concurrent worker tasks of the Sentri V2 Conversation Runtime,
    monitoring their health and coordinating graceful hierarchical cancellation.
    """
    def __init__(self, context: TurnContext, channels: TurnChannels):
        self.context = context
        self.channels = channels
        self.workers: Dict[str, Dict[str, asyncio.Task]] = {
            "reasoning": {},
            "synthesis": {}
        }
        self._monitor_task: asyncio.Task = None

    def start_worker(self, group: str, name: str, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self.workers[group][name] = task
        return task

    def start_monitoring(self):
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def _monitor_loop(self):
        try:
            while not self.context.cancel_token.is_set():
                await asyncio.sleep(0.5)
                # Check for failed workers
                for group, group_tasks in self.workers.items():
                    for name, task in group_tasks.items():
                        if task.done() and not task.cancelled():
                            exc = task.exception()
                            if exc:
                                logger.error(f"[SUPERVISOR] Worker {group}/{name} failed with exception: {exc}")
                                self.cancel_all()
                                return
        except asyncio.CancelledError:
            pass

    def cancel(self, target: str = "all"):
        """
        Supports hierarchical cancellation.
        - "all": Cancels all tasks.
        - "synthesis": Cancels TTS and playback/sends, preserving active reasoning.
        """
        logger.info(f"[SUPERVISOR] Hierarchical cancellation requested for target: {target}")
        if target in ("all", "reasoning"):
            for name, task in list(self.workers["reasoning"].items()):
                if not task.done():
                    task.cancel()
                    logger.debug(f"[SUPERVISOR] Cancelled worker: reasoning/{name}")
        
        if target in ("all", "synthesis"):
            for name, task in list(self.workers["synthesis"].items()):
                if not task.done():
                    task.cancel()
                    logger.debug(f"[SUPERVISOR] Cancelled worker: synthesis/{name}")

        if target == "all":
            self.context.cancel_token.set()
            if self._monitor_task and not self._monitor_task.done():
                self._monitor_task.cancel()

    def cancel_all(self):
        self.cancel("all")

    async def cleanup(self):
        self.cancel_all()
        # Await completion/cancellation of all tasks
        all_tasks = []
        if self._monitor_task:
            all_tasks.append(self._monitor_task)
        for group in self.workers.values():
            all_tasks.extend(group.values())
        
        if all_tasks:
            await asyncio.gather(*all_tasks, return_exceptions=True)

class ConversationRuntime(ISpeechToSpeechModel):
    """
    Sentri V2 Conversation Runtime. Coordinated concurrent execution of ASR, LLM, Chunker,
    and TTS workers, using TurnContext for state and TurnChannels for data.
    """
    def __init__(self):
        self.asr = ProviderRegistry.get_asr(ASR_PROVIDER)
        self.reasoning = ProviderRegistry.get_reasoning(REASONING_PROVIDER, model_name=REASONING_MODEL)
        self.tts = ProviderRegistry.get_tts(TTS_PROVIDER, voice_name=TTS_SPEAKER_VOICE)
        self.speech_planner = SpeechPlanner()
        self.event_bus = EventBus()

        self.prompt_builder = PromptBuilder()
        self.system_prompt_provider = SystemPromptProvider()
        self.memory_provider = MemoryProvider()

        from app.conversation.intent_analysis import IntentAnalyzer
        from app.conversation.retrieval_planner import RetrievalPlanner
        from app.conversation.quick_responses import QuickResponseEngine
        self.intent_analyzer = IntentAnalyzer()
        self.retrieval_planner = RetrievalPlanner()
        self.quick_response_engine = QuickResponseEngine()

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
        self.event_bus.subscribe(Interrupted, lambda e: logger.info(f"[{e.turn_id}] Interrupted"))
        self.event_bus.subscribe(Cancelled, lambda e: logger.info(f"[{e.turn_id}] Cancelled"))
        self.event_bus.subscribe(Error, lambda e: logger.error(f"[{e.turn_id}] Error: {e.message}"))

    async def process_audio_stream_with_text(
        self,
        audio_generator: AsyncGenerator[bytes, None],
        history: List[Dict[str, Any]] = None,
        websocket=None
    ) -> AsyncGenerator[Tuple[str, Union[bytes, str]], None]:
        """
        Coordinated real-time speech processing turn. Co-allocates LLM reasoning, SpeechPlanner,
        TTS streaming, and Web-Sockets audio pipeline.
        """
        turn_id = f"turn_{uuid.uuid4().hex[:8]}"
        context = TurnContext(turn_id=turn_id)
        channels = TurnChannels()
        supervisor = RuntimeSupervisor(context, channels)
        
        output_queue: asyncio.Queue[Tuple[str, Union[bytes, str, None]]] = asyncio.Queue()

        # Trace timestamps
        context.clock.mic_open_time = time.time()
        context.clock.speech_start_time = time.time()

        # 1. Capture raw PCM16 bytes in-memory (ASR buffer)
        pcm_bytes = bytearray()
        async for chunk in audio_generator:
            pcm_bytes.extend(chunk)

        context.user_audio = bytes(pcm_bytes)
        context.clock.speech_end_time = time.time()

        if not context.user_audio:
            logger.warning(f"[{turn_id}] Empty audio input stream.")
            return

        self.event_bus.publish(SpeechStarted(turn_id=turn_id))
        self.event_bus.publish(SpeechFinished(turn_id=turn_id))

        # 2. ASR Execution
        context.clock.asr_start_time = time.time()
        transcript = await self.asr.transcribe(context.user_audio)
        context.clock.asr_end_time = time.time()
        
        context.transcript = transcript
        self.event_bus.publish(TranscriptReady(turn_id=turn_id, text=transcript))

        if not transcript or not transcript.strip():
            logger.warning(f"[{turn_id}] No spoken words detected.")
            self.event_bus.publish(AudioFinished(turn_id=turn_id))
            return

        yield "user_transcript", transcript

        # 3. Context Preparation
        system_prompt = self.system_prompt_provider.build()
        context.system_prompt = system_prompt
        
        # Retrieve uploaded documents context
        docs_context = await asyncio.to_thread(self.memory_provider.retrieve)
        
        # Retrieve structured memory context from MemoryRuntime
        try:
            from app.memory.runtime import MemoryRuntime
            from app.memory.context_builder import MemoryContextBuilder
            from app.memory.contracts import MemoryQuery
            
            m_runtime = MemoryRuntime()
            intent = self.intent_analyzer.analyze(transcript)
            categories, budget = self.retrieval_planner.plan(intent)
            
            res_memories = []
            for category in categories:
                q = MemoryQuery(category=category, subject="user", limit=budget, include_inferred=True)
                res = m_runtime.recall(q)
                res_memories.extend(res.memories)
                
            structured_context = MemoryContextBuilder.build_context(res_memories, max_chars=4000, limit=budget)
        except Exception as e:
            logger.error(f"Failed to retrieve structured memories: {e}")
            structured_context = ""
            intent = "UNKNOWN_QUERY"

        # ── Quick Response Bypass ─────────────────────────────────
        # For deterministic intents (greetings, identity, time, etc.),
        # skip the LLM entirely and go straight to TTS.
        quick_response = self.quick_response_engine.respond(intent, transcript)
        if quick_response:
            logger.info(f"[{turn_id}] Quick response: '{quick_response}' (intent={intent})")
            # Bug #25: Stamp clock fields so TTFT/TTFA metrics are non-negative on bypass turns
            context.clock.llm_start_time = time.time()
            context.clock.first_token_time = time.time()
            context.clock.first_audio_frame_time = time.time()
            yield "text", quick_response
            # Synthesize TTS directly
            async for audio_bytes in self.tts.synthesize(quick_response):
                yield "audio", audio_bytes
            self.event_bus.publish(AudioFinished(turn_id=turn_id))
            return
        # ──────────────────────────────────────────────────────────
            
        combined_memory = docs_context
        if structured_context:
            if combined_memory:
                combined_memory += "\n" + structured_context
            else:
                combined_memory = structured_context
                
        context.memory_context = combined_memory
        context.clock.prompt_built_time = time.time()

        # Bug #1: Always send the original transcript — no intent-based rewrite.
        # Quick responses handle true greetings before the LLM is reached.
        model_input_transcript = transcript

        reasoning_request = self.prompt_builder.build(
            system_prompt=system_prompt,
            memory=combined_memory,
            history=history or [],
            transcript=model_input_transcript
        )
        self.event_bus.publish(ReasoningStarted(turn_id=turn_id))

        # ================= WORKERS DEFINITION =================

        async def llm_worker():
            """Streams LLM tokens, puts them to token_queue with queue delays."""
            first_token = True
            context.clock.llm_start_time = time.time()
            try:
                async for token in self.reasoning.stream(reasoning_request, websocket=websocket):
                    if context.cancel_token.is_set():
                        break
                    
                    if first_token:
                        context.clock.first_token_time = time.time()
                        first_token = False
                    
                    self.event_bus.publish(TokenGenerated(turn_id=turn_id, token=token))
                    
                    # Yield token to output immediately
                    await output_queue.put(("text", token))
                    
                    # Pass data plane token to SpeechPlanner with timestamp
                    await channels.token_queue.put((time.time(), token))
                    
                # Signal SpeechPlanner that LLM is complete
                await channels.token_queue.put((time.time(), None))
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"[{turn_id}] LLM Worker failed: {e}")
                await output_queue.put(("error", str(e)))
            finally:
                context.clock.llm_end_time = time.time()

        def clean_voice_phrase(text: str) -> str:
            from app.conversation.utils import ResponseCleaner
            return ResponseCleaner.clean(text)

        async def speech_planner_worker():
            """Consumes LLM tokens, plans acoustic chunks, and passes to TTS."""
            token_delays = []
            try:
                while not context.cancel_token.is_set():
                    t_added, token = await channels.token_queue.get()
                    token_delays.append(time.time() - t_added)
                    
                    if token is None:  # End of LLM stream
                        # Flush planner
                        remaining = self.speech_planner.flush()
                        if remaining:
                            cleaned_remaining = clean_voice_phrase(remaining)
                            if cleaned_remaining:
                                self.event_bus.publish(ChunkReady(turn_id=turn_id, text=cleaned_remaining))
                                await channels.phrase_queue.put((time.time(), cleaned_remaining))
                        # Signal TTS complete
                        await channels.phrase_queue.put((time.time(), None))
                        break
                    
                    async for phrase in self.speech_planner.feed(token):
                        if context.clock.first_phrase_time == 0.0:
                            context.clock.first_phrase_time = time.time()
                        cleaned_phrase = clean_voice_phrase(phrase)
                        if cleaned_phrase:
                            self.event_bus.publish(ChunkReady(turn_id=turn_id, text=cleaned_phrase))
                            await channels.phrase_queue.put((time.time(), cleaned_phrase))
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"[{turn_id}] SpeechPlanner Worker failed: {e}")
                await output_queue.put(("error", str(e)))
            finally:
                if token_delays:
                    avg_delay_ms = (sum(token_delays) / len(token_delays)) * 1000
                    logger.debug(f"[{turn_id}] SpeechPlanner Avg Token Queue Delay: {avg_delay_ms:.2f}ms")

        async def tts_worker():
            """Consumes phrases, streams TTS audio synthesis, and outputs to Playback queue."""
            phrase_delays = []
            first_audio = True
            context.clock.tts_start_time = time.time()
            try:
                while not context.cancel_token.is_set():
                    t_added, phrase = await channels.phrase_queue.get()
                    phrase_delays.append(time.time() - t_added)
                    
                    if phrase is None:  # End of phrases
                        await channels.audio_queue.put((time.time(), None))
                        break
                    
                    async for audio_chunk in self.tts.synthesize(phrase):
                        if context.cancel_token.is_set():
                            break
                        
                        if first_audio:
                            context.clock.first_audio_frame_time = time.time()
                            self.event_bus.publish(AudioStarted(turn_id=turn_id))
                            first_audio = False
                            
                        self.event_bus.publish(AudioChunkEvent(turn_id=turn_id, pcm_bytes=audio_chunk))
                        await channels.audio_queue.put((time.time(), audio_chunk))
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"[{turn_id}] TTS Worker failed: {e}")
                await output_queue.put(("error", str(e)))
            finally:
                context.clock.tts_end_time = time.time()
                if phrase_delays:
                    avg_delay_ms = (sum(phrase_delays) / len(phrase_delays)) * 1000
                    logger.debug(f"[{turn_id}] TTS Avg Phrase Queue Delay: {avg_delay_ms:.2f}ms")

        async def playback_worker():
            """Consumes audio, pushes to output_queue for WebSocket transmission."""
            audio_delays = []
            try:
                while not context.cancel_token.is_set():
                    t_added, audio_bytes = await channels.audio_queue.get()
                    if audio_bytes is None:  # Playback finish
                        context.clock.playback_finish_time = time.time()
                        await output_queue.put(("finish", None))
                        break
                    
                    audio_delays.append(time.time() - t_added)
                    if context.clock.playback_start_time == 0.0:
                        context.clock.playback_start_time = time.time()
                        
                    await output_queue.put(("audio", audio_bytes))
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"[{turn_id}] Playback Worker failed: {e}")
                await output_queue.put(("error", str(e)))
            finally:
                if audio_delays:
                    avg_delay_ms = (sum(audio_delays) / len(audio_delays)) * 1000
                    logger.debug(f"[{turn_id}] Playback Avg Audio Queue Delay: {avg_delay_ms:.2f}ms")

        # ================= SUPERVISOR START =================

        supervisor.start_worker("reasoning", "llm", llm_worker())
        supervisor.start_worker("reasoning", "speech_planner", speech_planner_worker())
        supervisor.start_worker("synthesis", "tts", tts_worker())
        supervisor.start_worker("synthesis", "playback", playback_worker())
        supervisor.start_monitoring()

        # ================= OUTPUT STREAM CONSUMER =================

        accumulated_text = []
        try:
            while not context.cancel_token.is_set():
                event_type, payload = await output_queue.get()
                
                if event_type == "finish":
                    break
                elif event_type == "error":
                    self.event_bus.publish(Error(turn_id=turn_id, message=str(payload)))
                    raise RuntimeError(payload)
                elif event_type == "text":
                    accumulated_text.append(payload)
                    yield "text", payload
                elif event_type == "audio":
                    yield "audio", payload
        except GeneratorExit:
            logger.info(f"[{turn_id}] Generator closed by client (Interrupted).")
            self.event_bus.publish(Interrupted(turn_id=turn_id))
            supervisor.cancel("all")
        finally:
            self.speech_planner.flush()  # Bug #21: clear/reset speech planner buffer to prevent bleed between turns
            await supervisor.cleanup()
            self.event_bus.publish(AudioFinished(turn_id=turn_id))
            context.reasoning_response = "".join(accumulated_text)
            
            # Print execution traces & clock measurements
            t_asr = (context.clock.asr_end_time - context.clock.asr_start_time) * 1000
            t_prompt = (context.clock.prompt_built_time - context.clock.asr_end_time) * 1000
            t_ttft = (context.clock.first_token_time - context.clock.llm_start_time) * 1000
            t_ttfa = (context.clock.first_audio_frame_time - context.clock.speech_end_time) * 1000
            t_total = (time.time() - context.clock.speech_end_time) * 1000
            
            logger.info(
                f"\n[SENTRI V2 EXECUTION TRACE] {turn_id}\n"
                f"  ASR Duration:         {t_asr:>8.0f} ms\n"
                f"  Prompt Build:         {t_prompt:>8.0f} ms\n"
                f"  LLM TTFT:             {t_ttft:>8.0f} ms\n"
                f"  Time to First Audio:  {t_ttfa:>8.0f} ms (From User Speech End)\n"
                f"  {'─'*40}\n"
                f"  Total Turn Latency:   {t_total:>8.0f} ms"
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

# Keep alias for backward compatibility
StreamingSpeechPipeline = ConversationRuntime
