package com.racas.mostwanted;

import org.junit.Test;

import static org.junit.Assert.*;

public class GinAudioTest {
    private static byte[] sample(String signature, long[] offsets, long indexedDataSize) {
        byte[] b = new byte[32 + offsets.length * 4 + 16];
        byte[] magic = signature.getBytes(java.nio.charset.StandardCharsets.US_ASCII);
        System.arraycopy(magic, 0, b, 0, magic.length);
        put32(b, 16, 50);
        put32(b, 20, offsets.length);
        put32(b, 24, indexedDataSize);
        put32(b, 28, 24000);
        for (int i = 0; i < offsets.length; i++) put32(b, 32 + i * 4, offsets[i]);
        return b;
    }

    private static void put32(byte[] b, int at, long value) {
        for (int i = 0; i < 4; i++) b[at + i] = (byte) (value >>> (8 * i));
    }

    @Test public void recognizesHeaderAndParsesIndexTable() {
        GinAudio.Result r = GinAudio.inspect(sample("Gnsu20",
                new long[]{0, 18399, 26286, 0, 1979}, 30000));
        assertEquals(GinAudio.Status.SUPPORTED_HEADER, r.status);
        assertEquals(5, r.indexCount);
        assertEquals(24000, r.sampleRate);
        assertEquals(52, r.payloadOffset);
        assertEquals(16, r.payloadSize);
        assertEquals(26286, r.maximumIndexOffset);
        assertTrue(r.hasStructurallyValidIndex());
    }

    @Test public void acceptsNonMonotonicOffsetsFoundInDecelSamples() {
        GinAudio.Result r = GinAudio.inspect(sample("Gnsu20",
                new long[]{30000, 28000, 0, 1000, 2000}, 32000));
        assertTrue(r.hasStructurallyValidIndex());
    }

    @Test public void accepts48000HzMostWantedAddonGinRate() {
        byte[] b = sample("Gnsu20", new long[]{0, 1000, 2000}, 3000);
        put32(b, 28, 48000);
        GinAudio.Result r = GinAudio.inspect(b);
        assertEquals(GinAudio.Status.SUPPORTED_HEADER, r.status);
        assertEquals(48000, r.sampleRate);
    }

    @Test public void repairsOnlyValidatedLegacySignatureOnCopy() {
        byte[] original = sample("Octn21", new long[]{0, 1000, 2000}, 3000);
        byte[] repaired = GinAudio.repairLegacyHeader(original);
        assertEquals(GinAudio.Status.LEGACY_HEADER, GinAudio.inspect(original).status);
        assertEquals(GinAudio.Status.SUPPORTED_HEADER, GinAudio.inspect(repaired).status);
        assertEquals('O', original[0]);
        assertEquals('G', repaired[0]);
        for (int i = 6; i < original.length; i++) assertEquals(original[i], repaired[i]);
    }

    @Test public void rejectsUnknownSignatureAndTruncatedHeader() {
        assertEquals(GinAudio.Status.INVALID,
                GinAudio.inspect(sample("BADBAD", new long[]{0, 100}, 200)).status);
        assertEquals(GinAudio.Status.INVALID, GinAudio.inspect(new byte[20]).status);
    }

    @Test public void rejectsTruncatedIndexTable() {
        byte[] b = sample("Gnsu20", new long[]{0, 100, 200}, 300);
        assertEquals(GinAudio.Status.INVALID, GinAudio.inspect(java.util.Arrays.copyOf(b, 40)).status);
    }

    @Test public void rejectsIndexOffsetOutsideDeclaredDataRange() {
        assertEquals(GinAudio.Status.INVALID,
                GinAudio.inspect(sample("Gnsu20", new long[]{0, 1001}, 1000)).status);
    }

    @Test public void rejectsInvalidSampleRate() {
        byte[] b = sample("Gnsu20", new long[]{0, 100}, 200);
        put32(b, 28, 0);
        assertEquals(GinAudio.Status.INVALID, GinAudio.inspect(b).status);
    }

    @Test(expected = IllegalArgumentException.class)
    public void willNotRewriteCurrentHeader() {
        GinAudio.repairLegacyHeader(sample("Gnsu20", new long[]{0, 100}, 200));
    }
}
