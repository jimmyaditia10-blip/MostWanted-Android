package com.racas.mostwanted;

import java.util.Arrays;

/**
 * Conservative reader for the fixed GIN header observed in NFS Heat samples.
 *
 * This class deliberately does not decode the audio payload. The 236 supplied
 * samples establish the magic, the 32-byte minimum header, format marker 50,
 * and 24 kHz sample rate; they do not establish the payload's codec or the
 * meaning of every header field.
 */
final class GinAudio {
    static final int HEADER_SIZE = 32;
    static final int FORMAT_MARKER = 50;
    static final long MIN_SAMPLE_RATE = 8_000;
    static final long MAX_SAMPLE_RATE = 192_000;

    private static final byte[] CURRENT = {'G', 'n', 's', 'u', '2', '0'};
    private static final byte[] LEGACY = {'O', 'c', 't', 'n', '2', '1'};

    enum Status {
        SUPPORTED_HEADER,
        LEGACY_HEADER,
        INVALID
    }

    static final class Result {
        final Status status;
        final String reason;
        final long formatMarker;
        final long entryCount;
        final long field24;
        final long sampleRate;

        private Result(Status status, String reason, long formatMarker,
                       long entryCount, long field24, long sampleRate) {
            this.status = status;
            this.reason = reason;
            this.formatMarker = formatMarker;
            this.entryCount = entryCount;
            this.field24 = field24;
            this.sampleRate = sampleRate;
        }

        boolean isValidHeader() {
            return status != Status.INVALID;
        }

        boolean needsLegacyRepair() {
            return status == Status.LEGACY_HEADER;
        }
    }

    private GinAudio() {}

    static Result inspect(byte[] data) {
        if (data == null || data.length < HEADER_SIZE)
            return invalid("GIN header is shorter than 32 bytes");

        boolean current = startsWith(data, CURRENT);
        boolean legacy = startsWith(data, LEGACY);
        if (!current && !legacy)
            return invalid("unrecognized GIN signature");

        long marker = u32(data, 16);
        long count = u32(data, 20);
        long field24 = u32(data, 24);
        long rate = u32(data, 28);

        if (marker != FORMAT_MARKER)
            return invalid("unsupported GIN header marker: " + marker);
        if (count == 0 || count > 65_536)
            return invalid("invalid GIN entry count: " + count);
        if (rate < MIN_SAMPLE_RATE || rate > MAX_SAMPLE_RATE)
            return invalid("invalid GIN sample rate: " + rate);

        return new Result(current ? Status.SUPPORTED_HEADER : Status.LEGACY_HEADER,
                current ? "GIN header recognized" : "legacy GIN header; signature repair may be applicable",
                marker, count, field24, rate);
    }

    /**
     * Returns a new byte array. Only the six-byte legacy signature is changed;
     * all other bytes remain identical. The input array is never modified.
     */
    static byte[] repairLegacyHeader(byte[] data) {
        Result result = inspect(data);
        if (!result.needsLegacyRepair())
            throw new IllegalArgumentException("only a validated Octn21 GIN header can be repaired");
        byte[] repaired = Arrays.copyOf(data, data.length);
        System.arraycopy(CURRENT, 0, repaired, 0, CURRENT.length);
        return repaired;
    }

    private static Result invalid(String reason) {
        return new Result(Status.INVALID, reason, 0, 0, 0, 0);
    }

    private static boolean startsWith(byte[] data, byte[] signature) {
        for (int i = 0; i < signature.length; i++)
            if (data[i] != signature[i]) return false;
        return true;
    }

    private static long u32(byte[] data, int offset) {
        return (data[offset] & 0xffL)
                | ((data[offset + 1] & 0xffL) << 8)
                | ((data[offset + 2] & 0xffL) << 16)
                | ((data[offset + 3] & 0xffL) << 24);
    }
}
