package com.racas.mostwanted;

import org.junit.Test;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.file.Files;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.junit.Assert.*;

public class ModArchiveTest {
    @Test public void preservesEveryRegularSourceFileWithoutFiltering() throws Exception {
        File root = Files.createTempDirectory("mod-archive-test").toFile();
        File archive = new File(root, "sample.zip");
        File spool = new File(root, "spool");
        byte[][] payloads = {
                "readme".getBytes(java.nio.charset.StandardCharsets.UTF_8),
                new byte[] {0, 1, 2, 3, (byte) 0xFF},
                new byte[] {9, 8, 7, 6},
                new byte[] {4, 3, 2, 1}
        };
        String[] names = {"readme.txt", "docs/manual.pdf", "unknown/data.bin", "SOUND/ENGINE/GIN_custom.gin"};
        try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(archive))) {
            for (int i = 0; i < names.length; i++) {
                zip.putNextEntry(new ZipEntry(names[i]));
                zip.write(payloads[i]);
                zip.closeEntry();
            }
        }

        try {
            Map<String, File> files = ModArchive.read(archive, spool);
            assertEquals(names.length, files.size());
            for (int i = 0; i < names.length; i++)
                assertArrayEquals(names[i], payloads[i], Files.readAllBytes(files.get(names[i]).toPath()));
        } finally {
            ModArchive.clear(spool);
            archive.delete();
            root.delete();
        }
    }
    @Test public void rejectsArchivePathTraversal() throws Exception {
        File root = Files.createTempDirectory("mod-archive-traversal").toFile();
        File archive = new File(root, "bad.zip");
        try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(archive))) {
            zip.putNextEntry(new ZipEntry("../escape.bin"));
            zip.write(new byte[] {1});
            zip.closeEntry();
        }
        try {
            ModArchive.read(archive, new File(root, "spool"));
            fail("path traversal must be rejected");
        } catch (java.io.IOException expected) {
            assertTrue(expected.getMessage().contains("unsafe archive entry path"));
        }
    }

    @Test public void rejectsCaseCollidingArchivePaths() throws Exception {
        File root = Files.createTempDirectory("mod-archive-case").toFile();
        File archive = new File(root, "case.zip");
        try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(archive))) {
            zip.putNextEntry(new ZipEntry("Assets/Install_Attributes"));
            zip.write(new byte[] {1});
            zip.closeEntry();
            zip.putNextEntry(new ZipEntry("assets/install_attributes"));
            zip.write(new byte[] {2});
            zip.closeEntry();
        }
        try {
            ModArchive.read(archive, new File(root, "spool"));
            fail("case collision must be rejected");
        } catch (java.io.IOException expected) {
            assertTrue(expected.getMessage().contains("case-colliding"));
        }
    }

}
