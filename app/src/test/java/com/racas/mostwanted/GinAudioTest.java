package com.racas.mostwanted;

import org.junit.Test;

import static org.junit.Assert.*;

public class GinAudioTest {
    private static byte[] header(String signature) {
        byte[] b = new byte[64];
        byte[] magic = signature.getBytes(java.nio.charset.StandardCharsets.US_ASCII);
        System.arraycopy(magic, 0, b, 0, magic.length);
        put32(b, 16, 50);
        put32(b, 20, 355);
        put32(b, 24, 262609);
        put32(b, 28, 24000);
        return b;
    }

    private static void put32(byte[] b, int at, long value) {
        for (int i = 0; i < 4; i++) b[at + i] = (byte) (value >>> (8 * i));
    }

    @Test public void recognizesHeatGinHeader() {
        GinAudio.Result r = GinAudio.inspect(header("Gnsu20"));
        assertEquals(GinAudio.Status.SUPPORTED_HEADER, r.status);
        assertEquals(355, r.entryCount);
        assertEquals(24000, r.sampleRate);
    }

    @Test public void repairsOnlyValidatedLegacySignatureOnCopy() {
        byte[] original = header("Octn21");
        byte[] repaired = GinAudio.repairLegacyHeader(original);
        assertEquals(GinAudio.Status.LEGACY_HEADER, GinAudio.inspect(original).status);
        assertEquals(GinAudio.Status.SUPPORTED_HEADER, GinAudio.inspect(repaired).status);
        assertEquals('O', original[0]);
        assertEquals('G', repaired[0]);
        for (int i = 6; i < original.length; i++) assertEquals(original[i], repaired[i]);
    }

    @Test public void rejectsUnknownSignatureAndTruncatedHeader() {
        assertEquals(GinAudio.Status.INVALID, GinAudio.inspect(header("BADBAD")).status);
        assertEquals(GinAudio.Status.INVALID, GinAudio.inspect(new byte[20]).status);
    }

    @Test public void rejectsInvalidSampleRate() {
        byte[] b = header("Gnsu20");
        put32(b, 28, 0);
        assertEquals(GinAudio.Status.INVALID, GinAudio.inspect(b).status);
    }

    @Test(expected = IllegalArgumentException.class)
    public void willNotRewriteCurrentHeader() {
        GinAudio.repairLegacyHeader(header("Gnsu20"));
    }
}
