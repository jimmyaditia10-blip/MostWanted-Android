package com.racas.mostwanted;

import java.util.Arrays;

/**
 * Conservative structural reader for the GIN samples supplied from NFS Heat.
 *
 * The samples establish a 32-byte header, a little-endian index table at byte
 * 32, format marker 50, and a 24 kHz sample rate. The indexed audio payload is
 * not decoded here: its codec and the meaning of the two leading float-like
 * header words still require independent format research.
 */
final class GinAudio {
    static final int HEADER_SIZE = 32;
    static final int FORMAT_MARKER = 50;
    static final long MIN_SAMPLE_RATE = 8_000;
    static final long MAX_SAMPLE_RATE = 192_000;
    static final long MAX_INDEX_COUNT = 65_536;

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
        final long indexCount;
        final long indexedDataSize;
        final long sampleRate;
        final int indexTableOffset;
        final int payloadOffset;
        final long payloadSize;
        final long maximumIndexOffset;
        final long[] indexOffsets;

        private Result(Status status, String reason, long formatMarker,
                       long indexCount, long indexedDataSize, long sampleRate,
                       int indexTableOffset, int payloadOffset, long payloadSize,
                       long maximumIndexOffset, long[] indexOffsets) {
            this.status = status;
            this.reason = reason;
            this.formatMarker = formatMarker;
            this.indexCount = indexCount;
            this.indexedDataSize = indexedDataSize;
            this.sampleRate = sampleRate;
            this.indexTableOffset = indexTableOffset;
            this.payloadOffset = payloadOffset;
            this.payloadSize = payloadSize;
            this.maximumIndexOffset = maximumIndexOffset;
            this.indexOffsets = indexOffsets;
        }

        boolean isValidHeader() {
            return status != Status.INVALID;
        }

        boolean hasStructurallyValidIndex() {
            return isValidHeader() && indexOffsets != null && payloadSize > 0;
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
        long indexedDataSize = u32(data, 24);
        long rate = u32(data, 28);

        if (marker != FORMAT_MARKER)
            return invalid("unsupported GIN format marker: " + marker);
        if (count == 0 || count > MAX_INDEX_COUNT)
            return invalid("invalid GIN index count: " + count);
        if (indexedDataSize == 0)
            return invalid("empty indexed audio data size");
        if (rate < MIN_SAMPLE_RATE || rate > MAX_SAMPLE_RATE)
            return invalid("invalid GIN sample rate: " + rate);

        long tableEndLong = HEADER_SIZE + count * 4L;
        if (tableEndLong >= data.length || tableEndLong > Integer.MAX_VALUE)
            return invalid("GIN index table is truncated or has no payload");

        int payloadOffset = (int) tableEndLong;
        long[] offsets = new long[(int) count];
        long maxOffset = 0;
        for (int i = 0; i < offsets.length; i++) {
            long value = u32(data, HEADER_SIZE + i * 4);
            if (value > indexedDataSize)
                return invalid("GIN index offset exceeds indexed data size at entry " + i);
            offsets[i] = value;
            if (value > maxOffset) maxOffset = value;
        }

        // Do not require sorted offsets: the supplied DECEL samples contain
        // descending and ascending index runs, so ordering is format-dependent.
        return new Result(
                current ? Status.SUPPORTED_HEADER : Status.LEGACY_HEADER,
                current ? "GIN header and index table recognized"
                        : "legacy GIN header and index table recognized",
                marker, count, indexedDataSize, rate,
                HEADER_SIZE, payloadOffset, data.length - (long) payloadOffset,
                maxOffset, offsets);
    }

    /**
     * Returns a new byte array. Only the six-byte legacy signature is changed;
     * all other bytes remain identical. The input array is never modified.
     */
    static byte[] repairLegacyHeader(byte[] data) {
        Result result = inspect(data);
        if (!result.needsLegacyRepair())
            throw new IllegalArgumentException("only a validated Octn21 GIN file can be repaired");
        byte[] repaired = Arrays.copyOf(data, data.length);
        System.arraycopy(CURRENT, 0, repaired, 0, CURRENT.length);
        return repaired;
    }

    private static Result invalid(String reason) {
        return new Result(Status.INVALID, reason, 0, 0, 0, 0,
                HEADER_SIZE, 0, 0, 0, null);
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
