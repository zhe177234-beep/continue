package cn.zhixue;

import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import java.net.InetSocketAddress;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.junit.jupiter.api.Assertions.*;

class GatewayControllerTest {
    @Test
    void forwardsBodyCookiesAndStatus() throws Exception {
        HttpServer stub = HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        stub.createContext("/api/auth/login",exchange->{
            assertEquals("POST",exchange.getRequestMethod());
            assertEquals("session=abc",exchange.getRequestHeaders().getFirst("Cookie"));
            byte[] body=exchange.getRequestBody().readAllBytes();
            exchange.getResponseHeaders().add("Set-Cookie","session=new; HttpOnly; SameSite=Strict; Path=/");
            exchange.getResponseHeaders().add("Content-Type","application/json");
            exchange.sendResponseHeaders(201,body.length);exchange.getResponseBody().write(body);exchange.close();
        });
        stub.start();
        try {
            var mvc=MockMvcBuilders.standaloneSetup(new GatewayController("http://127.0.0.1:"+stub.getAddress().getPort())).build();
            mvc.perform(post("/api/auth/login").contentType("application/json").header("Cookie","session=abc").content("{\"test\":true}"))
                .andExpect(status().isCreated()).andExpect(content().json("{\"test\":true}"))
                .andExpect(header().string("Set-Cookie",org.hamcrest.Matchers.allOf(org.hamcrest.Matchers.containsString("session=new"),org.hamcrest.Matchers.containsString("HttpOnly"),org.hamcrest.Matchers.containsString("SameSite=Strict"),org.hamcrest.Matchers.containsString("Path=/"))));
        } finally { stub.stop(0); }
    }

    @Test
    void rejectsCrossOriginAndUnsupportedMethods() throws Exception {
        var mvc=MockMvcBuilders.standaloneSetup(new GatewayController("http://127.0.0.1:1")).build();
        mvc.perform(post("/api/bases").header("Host","localhost:8080").header("Origin","https://evil.example").content("{}"))
            .andExpect(status().isForbidden());
        mvc.perform(put("/api/bases")).andExpect(status().isMethodNotAllowed());
    }

    @Test
    void returnsReadableUpstreamFailure() throws Exception {
        var mvc=MockMvcBuilders.standaloneSetup(new GatewayController("http://127.0.0.1:1")).build();
        mvc.perform(get("/api/health")).andExpect(status().isBadGateway()).andExpect(content().contentTypeCompatibleWith("application/json"));
    }

    @Test
    void allowsTenMibMultipartAndRejectsOversizedBody() throws Exception {
        HttpServer stub = HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        stub.createContext("/api/bases/test/documents",exchange->{
            int size=exchange.getRequestBody().readAllBytes().length;
            assertEquals(10*1024*1024+1024,size);
            byte[] response="{}".getBytes(java.nio.charset.StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(201,response.length);
            exchange.getResponseBody().write(response);exchange.close();
        });
        stub.start();
        try {
            var mvc=MockMvcBuilders.standaloneSetup(new GatewayController("http://127.0.0.1:"+stub.getAddress().getPort())).build();
            mvc.perform(post("/api/bases/test/documents").contentType("multipart/form-data; boundary=test").content(new byte[10*1024*1024+1024]))
                .andExpect(status().isCreated());
            mvc.perform(post("/api/bases/test/documents").content(new byte[10*1024*1024+65537]))
                .andExpect(status().isPayloadTooLarge());
        } finally { stub.stop(0); }
    }
}
