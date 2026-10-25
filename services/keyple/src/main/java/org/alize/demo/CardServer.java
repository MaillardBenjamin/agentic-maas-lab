package org.alize.demo;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicReference;
import org.eclipse.keyple.card.calypso.CalypsoExtensionService;
import org.eclipse.keyple.core.service.SmartCardServiceProvider;
import org.eclipse.keyple.core.util.HexUtil;
import org.eclipse.keyple.plugin.stub.StubPluginFactoryBuilder;
import org.eclipse.keyple.plugin.stub.StubSmartCard;
import org.eclipse.keypop.calypso.card.card.CalypsoCard;

/** Original demo adapter. Card/SAM security and transport data model are simulated. */
public class CardServer {
  private static final String AID = "315449432E49434131";

  public static synchronized String exercise(byte[] record) {
    if (record.length != 28) throw new IllegalArgumentException("28 byte fixture required");
    var current = new AtomicReference<>(new byte[28]);
    var card = StubSmartCard.builder()
        .withPowerOnData(HexUtil.toByteArray("3B888001000000009171710098"))
        .withProtocol("ISO_14443_4_CARD")
        .withApduResponseProvider(apdu -> {
          if (apdu.equals("00A4040009" + AID + "00"))
            return "6F238409" + AID + "A516BF0C13C70800000000AABBCCDD53070A3C23051410019000";
          if (apdu.equals("00B2013C00")) return HexUtil.toHex(current.get()) + "9000";
          if (apdu.startsWith("00DC013C1C") && apdu.length() == 66) {
            current.set(HexUtil.toByteArray(apdu.substring(10)));
            return "9000";
          }
          if (apdu.equals("00C0000000")) return "9000";
          throw new IllegalStateException("Unexpected APDU " + apdu.substring(0, Math.min(10, apdu.length())));
        }).build();
    var service = SmartCardServiceProvider.getService();
    var plugin = service.registerPlugin(StubPluginFactoryBuilder.builder().withStubReader("demo", true, card).build());
    try {
      var reader = plugin.getReader("demo");
      var factory = CalypsoExtensionService.getInstance().getCalypsoCardApiFactory();
      service.checkCardExtension(CalypsoExtensionService.getInstance());
      var selection = service.getReaderApiFactory().createCardSelectionManager();
      selection.prepareSelection(service.getReaderApiFactory().createIsoCardSelector().filterByDfName(AID), factory.createCalypsoCardSelectionExtension().prepareReadRecord((byte) 7, 1));
      var selected = (CalypsoCard) selection.processCardSelectionScenario(reader).getActiveSmartCard();
      if (selected == null) throw new IllegalStateException("Card selection failed");
      factory.createFreeTransactionManager(reader, selected).prepareUpdateRecord((byte) 7, 1, record).processCommands(org.eclipse.keypop.reader.ChannelControl.KEEP_OPEN);
      factory.createFreeTransactionManager(reader, selected).prepareReadRecord((byte) 7, 1).processCommands(org.eclipse.keypop.reader.ChannelControl.CLOSE_AFTER);
      if (!Arrays.equals(record, selected.getFileBySfi((byte) 7).getData().getContent(1))) throw new IllegalStateException("Read after write mismatch");
      return HexUtil.toHex(selected.getApplicationSerialNumber());
    } finally {
      service.unregisterPlugin(plugin.getName());
    }
  }

  public static void main(String[] args) throws Exception {
    var server = HttpServer.create(new InetSocketAddress(8004), 0);
    server.createContext("/health", exchange -> {
      var bytes = "{\"status\":\"ok\",\"mode\":\"real_sdk_stub_card\"}".getBytes(StandardCharsets.UTF_8);
      exchange.sendResponseHeaders(200, bytes.length); exchange.getResponseBody().write(bytes); exchange.close();
    });
    server.createContext("/load", exchange -> {
      try {
        if (!exchange.getRequestMethod().equals("POST")) throw new IllegalArgumentException("POST required");
        var bytes = exchange.getRequestBody().readNBytes(4000);
        var record = Arrays.copyOf(MessageDigest.getInstance("SHA-256").digest(bytes), 28);
        var serial = exercise(record);
        var body = ("{\"sdk\":\"Eclipse Keyple\",\"mode\":\"real_sdk_stub_card\",\"serial\":\"" + serial + "\",\"verified_read_after_write\":true}").getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(200, body.length); exchange.getResponseBody().write(body);
      } catch (Exception e) {
        var error = "{\"error\":\"Keyple stub transaction failed\"}".getBytes(StandardCharsets.UTF_8);
        exchange.sendResponseHeaders(500, error.length); exchange.getResponseBody().write(error);
      } finally { exchange.close(); }
    });
    server.start();
  }
}
