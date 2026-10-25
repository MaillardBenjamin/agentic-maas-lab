package org.alize.demo;
import static org.junit.jupiter.api.Assertions.*;
import org.junit.jupiter.api.Test;

class CardServerTest {
  @Test void sdkSelectsWritesAndReadsStub() {
    byte[] contract = new byte[28]; contract[0] = 0x42; contract[27] = 0x19;
    assertEquals("00000000AABBCCDD", CardServer.exercise(contract));
  }
  @Test void unsupportedRecordRejected() {
    assertThrows(IllegalArgumentException.class, () -> CardServer.exercise(new byte[27]));
  }
}
