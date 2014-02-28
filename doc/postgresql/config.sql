--
-- Name: config; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE config (
    id integer NOT NULL,
    section text NOT NULL,
    server text,
    channel text,
    key text NOT NULL,
    value text
);


--
-- Name: config_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE config_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: config_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE config_id_seq OWNED BY config.id;


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY config ALTER COLUMN id SET DEFAULT nextval('config_id_seq'::regclass);


--
-- Name: config_section_channel_key_idx; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE UNIQUE INDEX config_section_channel_key_idx ON config USING btree (section, channel, key) WHERE ((server IS NULL) AND (channel IS NOT NULL));


--
-- Name: config_section_key_idx; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE UNIQUE INDEX config_section_key_idx ON config USING btree (section, key) WHERE ((server IS NULL) AND (channel IS NULL));


--
-- Name: config_section_server_channel_key_idx; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE UNIQUE INDEX config_section_server_channel_key_idx ON config USING btree (section, server, channel, key) WHERE ((server IS NOT NULL) AND (channel IS NOT NULL));


--
-- Name: config_section_server_key_idx; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE UNIQUE INDEX config_section_server_key_idx ON config USING btree (section, server, key) WHERE ((server IS NOT NULL) AND (channel IS NULL));


--
-- PostgreSQL database dump complete
--

