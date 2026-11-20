package com.racas.mostwanted;

import org.junit.Test;
import static org.junit.Assert.*;

public class CarConverterReferenceKeyTest {
    @Test public void parsesNullReferenceAsZero() {
        assertEquals(0, CarConverter.referenceKey("0"));
        assertEquals(0, CarConverter.referenceKey("0x00000000"));
    }

    @Test public void parsesExplicitUnsignedHash() {
        assertEquals(0xd6b69989, CarConverter.referenceKey("0xd6b69989"));
        assertEquals(0xFFFFFFFF, CarConverter.referenceKey("0xffffffff"));
    }

    @Test public void hashesNamedCollectionReferences() {
        assertEquals(CarConverter.attribKey("GALLARDO"), CarConverter.referenceKey("GALLARDO"));
    }

    @Test(expected = NumberFormatException.class)
    public void rejectsMalformedExplicitHash() {
        CarConverter.referenceKey("0xnot-a-hash");
    }
}
